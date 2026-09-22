"""Smoke tooling for one migration head and a disposable empty database.

Run from the repository/deployment directory containing alembic.ini. This
command refuses existing tables/views and never drops a database or schema.
Tested against disposable PostgreSQL in test_migrations.py.
"""

import asyncio

from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import inspect

from marketing_ai.core.config import ConfigurationError, load_settings
from marketing_ai.infrastructure.database.session import Database


class MigrationCheckError(RuntimeError):
    """Controlled diagnostics without raw DB errors or URLs."""


def single_head(config: Config) -> str:
    heads = ScriptDirectory.from_config(config).get_heads()
    if len(heads) != 1:
        raise MigrationCheckError("Expected exactly one migration head")
    return heads[0]


async def check_database(*, expected_head: str | None) -> None:
    database = Database(load_settings())
    try:
        async with database.engine.connect() as connection:
            if expected_head is None:
                occupied = await connection.run_sync(
                    lambda conn: bool(
                        inspect(conn).get_table_names() or inspect(conn).get_view_names()
                    )
                )
                if occupied:
                    raise MigrationCheckError(
                        "Migration smoke requires an empty disposable database"
                    )
            else:
                heads = await connection.run_sync(
                    lambda conn: MigrationContext.configure(conn).get_current_heads()
                )
                if heads != (expected_head,):
                    raise MigrationCheckError("Database did not reach the single migration head")
    finally:
        await database.close()


def smoke(config: Config) -> None:
    head = single_head(config)
    asyncio.run(check_database(expected_head=None))
    command.upgrade(config, "head")
    asyncio.run(check_database(expected_head=head))


def main() -> None:
    try:
        smoke(Config("alembic.ini"))
    except (ConfigurationError, MigrationCheckError) as exc:
        raise SystemExit(str(exc)) from None
    except Exception:
        raise SystemExit(
            "Migration smoke failed; check database access and revision consistency"
        ) from None
    print("Migration smoke: PASS")


if __name__ == "__main__":
    main()
