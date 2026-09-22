"""Exercise packaging/security configuration with isolated filesystem inputs.

Uses real uv, Git and Compose configuration parsing, but no Docker daemon,
database or caller credentials. It never reads the developer's actual .env.
"""

import json
import os
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def test_git_ignore_preserves_templates_but_excludes_secrets(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True, timeout=15)
    shutil.copyfile(ROOT / ".gitignore", tmp_path / ".gitignore")
    for path in (".env", ".env.local", "nested/.env.production", ".venv/bin/python"):
        result = subprocess.run(
            ["git", "-C", str(tmp_path), "check-ignore", "-q", path], timeout=15
        )
        assert result.returncode == 0, path
    for path in (".env.example", "uv.lock", "src/marketing_ai/main.py"):
        result = subprocess.run(
            ["git", "-C", str(tmp_path), "check-ignore", "-q", path], timeout=15
        )
        assert result.returncode == 1, path


def test_example_has_no_database_password() -> None:
    values = dict(
        line.split("=", 1)
        for line in (ROOT / ".env.example").read_text().splitlines()
        if line and not line.startswith("#")
    )
    assert {"POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD"} <= values.keys()
    assert values["POSTGRES_PASSWORD"] == ""


def test_readme_setup_preserves_existing_local_env(tmp_path: Path) -> None:
    command = "test -e .env || cp .env.example .env"
    assert command in (ROOT / "README.md").read_text()
    example = "POSTGRES_PASSWORD=\n"
    (tmp_path / ".env.example").write_text(example)
    subprocess.run(["sh", "-c", command], cwd=tmp_path, check=True, timeout=10)
    assert (tmp_path / ".env").read_text() == example
    configured = "POSTGRES_PASSWORD=p01-synthetic-local-value\n"
    (tmp_path / ".env").write_text(configured)
    subprocess.run(["sh", "-c", command], cwd=tmp_path, check=True, timeout=10)
    assert (tmp_path / ".env").read_text() == configured


def test_locked_metadata_rejects_drift_without_rewriting_lock(tmp_path: Path) -> None:
    for filename in ("pyproject.toml", "uv.lock", "README.md"):
        shutil.copyfile(ROOT / filename, tmp_path / filename)
    shutil.copytree(ROOT / "src", tmp_path / "src", ignore=shutil.ignore_patterns("__pycache__"))
    command = [
        "uv",
        "lock",
        "--check",
        "--offline",
        "--project",
        str(tmp_path),
        "--python",
        sys.executable,
        "--cache-dir",
        str(tmp_path / "cache"),
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    original_lock = (tmp_path / "uv.lock").read_bytes()
    metadata = (tmp_path / "pyproject.toml").read_text()
    version = tomllib.loads(metadata)["project"]["version"]
    (tmp_path / "pyproject.toml").write_text(
        metadata.replace(f'version = "{version}"', f'version = "{version}.post1"', 1)
    )
    result = subprocess.run(command, capture_output=True, text=True, timeout=30)
    assert result.returncode != 0
    # With an empty offline cache uv may report unavailable resolver metadata;
    # either way drift must fail instead of silently updating the lockfile.
    assert (tmp_path / "uv.lock").read_bytes() == original_lock


@pytest.fixture
def compose_project(
    tmp_path: Path, database_test_values: dict[str, str], identity_test_values: dict[str, str]
) -> Path:
    shutil.copyfile(ROOT / "docker-compose.yml", tmp_path / "docker-compose.yml")
    shutil.copyfile(ROOT / ".env.example", tmp_path / ".env")
    with (tmp_path / ".env").open("a") as environment:
        environment.write(
            "\n" + "\n".join(f"{key}={value}" for key, value in database_test_values.items())
        )
        environment.write(
            "\n" + "\n".join(f"{key}={value}" for key, value in identity_test_values.items())
        )
        environment.write("\nCOMPOSE_DATABASE_URL=" + database_test_values["DATABASE_URL"] + "\n")
    return tmp_path


def compose_config(project: Path, password: str | None) -> subprocess.CompletedProcess[str]:
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("POSTGRES_", "COMPOSE_"))
    }
    if password is not None:
        environment["POSTGRES_PASSWORD"] = password
    return subprocess.run(
        [
            "docker",
            "compose",
            "--project-directory",
            str(project),
            "--env-file",
            str(project / ".env"),
            "--profile",
            "app",
            "config",
            "--format",
            "json",
        ],
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_compose_is_local_and_app_does_not_receive_database_credentials(
    compose_project: Path,
) -> None:
    result = compose_config(compose_project, "p01-placeholder-not-a-secret")
    assert result.returncode == 0, result.stderr
    services = json.loads(result.stdout)["services"]
    assert set(services) == {"app", "postgres", "redis"}
    assert services["app"]["profiles"] == ["app"]
    assert services["app"]["read_only"] is True
    assert services["app"]["cap_drop"] == ["ALL"]
    assert "no-new-privileges:true" in services["app"]["security_opt"]
    assert not {"POSTGRES_PASSWORD", "REDIS_URL"} & services["app"]["environment"].keys()
    assert services["app"]["environment"]["DATABASE_URL"].startswith("postgresql+psycopg://")
    for service in services.values():
        assert all(port["host_ip"] == "127.0.0.1" for port in service["ports"])
    assert services["postgres"]["volumes"][0]["type"] == "volume"
    assert services["redis"]["command"] == ["redis-server", "--save", "", "--appendonly", "no"]


def test_compose_allows_dependency_only_start_without_app_configuration(tmp_path: Path) -> None:
    """Profiles do not defer interpolation, so optional app values must remain runtime-validated."""
    shutil.copyfile(ROOT / "docker-compose.yml", tmp_path / "docker-compose.yml")
    (tmp_path / ".env").write_text("POSTGRES_PASSWORD=p01-placeholder-not-a-secret\n")
    result = subprocess.run(
        [
            "docker",
            "compose",
            "--project-directory",
            str(tmp_path),
            "--env-file",
            str(tmp_path / ".env"),
            "config",
            "--services",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert set(result.stdout.split()) == {"postgres", "redis"}


def test_base_compose_defers_empty_password_to_postgres_runtime(compose_project: Path) -> None:
    result = compose_config(compose_project, None)
    assert result.returncode == 0, result.stderr
    assert (
        json.loads(result.stdout)["services"]["postgres"]["environment"]["POSTGRES_PASSWORD"] == ""
    )


def test_docker_only_development_overlay_uses_trust_without_forwarding_credentials(
    tmp_path: Path,
) -> None:
    shutil.copyfile(ROOT / "docker-compose.yml", tmp_path / "docker-compose.yml")
    shutil.copyfile(ROOT / "docker-compose.dev.yml", tmp_path / "docker-compose.dev.yml")
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("POSTGRES_", "COMPOSE_", "DATABASE_", "IDENTITY_"))
    }
    result = subprocess.run(
        [
            "docker",
            "compose",
            "--project-directory",
            str(tmp_path),
            "-f",
            str(tmp_path / "docker-compose.yml"),
            "-f",
            str(tmp_path / "docker-compose.dev.yml"),
            "--profile",
            "app",
            "config",
            "--format",
            "json",
        ],
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    services = json.loads(result.stdout)["services"]
    assert services["postgres"]["environment"]["POSTGRES_HOST_AUTH_METHOD"] == "trust"
    assert services["postgres"]["environment"]["POSTGRES_PASSWORD"] == ""
    assert "POSTGRES_PASSWORD" not in services["app"]["environment"]
    assert services["app"]["environment"]["DATABASE_URL"].endswith("@postgres:5432/marketing_ai")
