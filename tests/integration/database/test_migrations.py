"""Real empty-database migration and metadata checks; no developer database."""

import asyncio
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.engine import URL

from marketing_ai.core.config import load_settings
from marketing_ai.infrastructure.database.migrations import MigrationCheckError, single_head, smoke
from marketing_ai.infrastructure.database.session import Database

pytestmark = pytest.mark.database
ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def migration_config(
    settings_values: dict[str, Any],
    postgres_url: URL,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Config:
    values = settings_values | {"DATABASE_URL": postgres_url.render_as_string(hide_password=False)}
    for key, value in values.items():
        monkeypatch.setenv(key, str(value))
    monkeypatch.chdir(tmp_path)  # No real .env is read, even by Alembic's settings loader.
    ini = tmp_path / "alembic.ini"
    ini.write_text(f"[alembic]\nscript_location = {ROOT / 'migrations'}\npath_separator = os\n")
    return Config(str(ini))


def test_empty_database_migrates_to_head_and_matches_metadata(migration_config: Config) -> None:
    smoke(migration_config)
    command.upgrade(migration_config, "head")  # Already-at-head is a no-op.
    command.check(migration_config)

    async def verify() -> None:
        database = Database(load_settings())
        try:
            async with database.engine.connect() as connection:
                tables = await connection.run_sync(lambda conn: inspect(conn).get_table_names())
                assert tables == ["alembic_version", "meta_connections", "meta_ad_account_links"]
                assert await connection.scalar(
                    text("SELECT version_num FROM alembic_version")
                ) == single_head(migration_config)
        finally:
            await database.close()

    asyncio.run(verify())
    with pytest.raises(MigrationCheckError, match="empty disposable"):
        smoke(migration_config)
    command.downgrade(migration_config, "base")
    command.upgrade(migration_config, "head")


def test_smoke_cli_uses_environment_url_with_percent_encoded_password(
    migration_config: Config,
) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "marketing_ai.infrastructure.database.migrations"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "Migration smoke: PASS"
    assert "%special" not in result.stdout + result.stderr


def test_failed_alembic_command_does_not_leak_database_url(
    migration_config: Config, monkeypatch: pytest.MonkeyPatch
) -> None:
    secret = "p03-migration-password-canary"
    monkeypatch.setenv("DATABASE_URL", f"postgresql+psycopg://test:{secret}@127.0.0.1:1/missing")
    assert migration_config.config_file_name is not None
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "alembic",
            "-c",
            migration_config.config_file_name,
            "upgrade",
            "head",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode != 0
    assert "Migration failed; check database access and revision consistency" in (
        result.stdout + result.stderr
    )
    assert secret not in result.stdout + result.stderr


def test_multiple_heads_are_detected_before_any_database_change(
    migration_config: Config, tmp_path: Path
) -> None:
    directory = tmp_path / "branched"
    shutil.copytree(ROOT / "migrations", directory)
    (directory / "versions" / "unmerged.py").write_text(
        'revision = "unmerged"\ndown_revision = None\nbranch_labels = None\ndepends_on = None\n'
        "def upgrade():\n    pass\ndef downgrade():\n    pass\n"
    )
    migration_config.set_main_option("script_location", str(directory))
    with pytest.raises(MigrationCheckError, match="exactly one"):
        smoke(migration_config)

    async def verify_empty() -> None:
        database = Database(load_settings())
        try:
            async with database.engine.connect() as connection:
                assert await connection.run_sync(lambda conn: inspect(conn).get_table_names()) == []
        finally:
            await database.close()

    asyncio.run(verify_empty())
