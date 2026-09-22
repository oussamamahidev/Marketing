"""Own one bounded async engine and fresh sessions for each request/task.

Used by app/worker composition and the API session dependency. No import-time
connections, shared AsyncSession, schema creation or automatic commit. Real
PostgreSQL behavior is covered by tests/integration/database/test_session.py.
"""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from time import perf_counter

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from marketing_ai.core.config import Settings
from marketing_ai.infrastructure.database.metrics import CHECK_DURATION, CHECKS


class Database:
    def __init__(self, settings: Settings) -> None:
        self.engine = create_async_engine(
            settings.DATABASE_URL.get_secret_value(),
            pool_size=settings.DATABASE_POOL_SIZE,
            max_overflow=settings.DATABASE_MAX_OVERFLOW,
            pool_timeout=settings.DATABASE_POOL_TIMEOUT_SECONDS,
            pool_pre_ping=True,
            echo=False,
            hide_parameters=True,
            connect_args={"connect_timeout": settings.DATABASE_CONNECT_TIMEOUT_SECONDS},
        )
        self.session_factory = async_sessionmaker(
            self.engine, expire_on_commit=False, autoflush=False
        )
        self.readiness_timeout = settings.DATABASE_READINESS_TIMEOUT_SECONDS

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        # Session exit rolls back uncommitted work and releases the connection.
        async with self.session_factory() as session:
            yield session

    async def check_ready(self) -> bool:
        started = perf_counter()
        outcome = "failure"
        try:
            async with asyncio.timeout(self.readiness_timeout):
                async with self.engine.connect() as connection:
                    result = await connection.scalar(text("SELECT 1"))
            outcome = "success" if result == 1 else "failure"
            return outcome == "success"
        except asyncio.CancelledError:
            outcome = "cancelled"
            raise
        except Exception:
            # The outer readiness runner emits the controlled failure event.
            return False
        finally:
            CHECKS.labels(outcome).inc()
            CHECK_DURATION.labels(outcome).observe(perf_counter() - started)

    async def close(self) -> None:
        await self.engine.dispose()
