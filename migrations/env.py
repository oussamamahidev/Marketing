"""Run Alembic with application metadata and a secret environment URL.

Only the migration process owns DDL. No app startup migrations; no credential
interpolation through ConfigParser and no raw SQL/driver exception logging.
"""

import asyncio

from alembic import context
from alembic.util import CommandError
from sqlalchemy import Connection, pool
from sqlalchemy.ext.asyncio import create_async_engine

from marketing_ai.core.config import load_settings
from marketing_ai.infrastructure.database.base import Base

settings = load_settings()
target_metadata = Base.metadata


def run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_online() -> None:
    engine = create_async_engine(
        settings.DATABASE_URL.get_secret_value(),
        poolclass=pool.NullPool,
        echo=False,
        hide_parameters=True,
        connect_args={"connect_timeout": settings.DATABASE_CONNECT_TIMEOUT_SECONDS},
    )
    try:
        async with engine.connect() as connection:
            await connection.run_sync(run_migrations)
    finally:
        await engine.dispose()


try:
    if context.is_offline_mode():
        context.configure(
            dialect_name="postgresql",
            target_metadata=target_metadata,
            literal_binds=True,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()
    else:
        asyncio.run(run_online())
except Exception:
    raise CommandError("Migration failed; check database access and revision consistency") from None
