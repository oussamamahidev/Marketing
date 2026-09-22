"""Exercise real PostgreSQL commits, rollback, isolation, pool bounds and health."""

import asyncio
import socket
from collections.abc import AsyncIterator
from typing import Annotated, Any

import pytest
from fastapi import Depends
from httpx2 import ASGITransport, AsyncClient
from prometheus_client import REGISTRY
from sqlalchemy import Column, Integer, MetaData, Table, Text, func, select, text
from sqlalchemy.engine import URL
from sqlalchemy.exc import IntegrityError
from sqlalchemy.exc import TimeoutError as PoolTimeout
from sqlalchemy.ext.asyncio import AsyncSession

from marketing_ai.api.dependencies import get_session
from marketing_ai.core.config import Settings
from marketing_ai.infrastructure.database.session import Database
from marketing_ai.infrastructure.database.transaction import transaction
from marketing_ai.main import create_app

pytestmark = [pytest.mark.database, pytest.mark.anyio]

# Test-only metadata proves DB behavior without introducing product tables.
metadata = MetaData()
probe = Table(
    "transaction_probe", metadata, Column("id", Integer, primary_key=True), Column("value", Text)
)


@pytest.fixture
def db_settings(settings_values: dict[str, Any], postgres_url: URL) -> Settings:
    return Settings(
        _env_file=None,
        **(settings_values | {"DATABASE_URL": postgres_url.render_as_string(hide_password=False)}),
    )


@pytest.fixture
async def database(db_settings: Settings) -> AsyncIterator[Database]:
    database = Database(db_settings)
    try:
        async with database.engine.begin() as connection:
            await connection.run_sync(metadata.create_all)
        yield database
    finally:
        await database.close()


async def count_rows(database: Database) -> int:
    async with database.session() as session:
        return int(await session.scalar(select(func.count()).select_from(probe)) or 0)


async def test_commit_and_parameterized_values(database: Database) -> None:
    malicious = "'); DROP TABLE transaction_probe; --"
    async with database.session() as session:
        async with transaction(session):
            await session.execute(probe.insert().values(id=1, value=malicious))
    async with database.session() as session:
        assert await session.scalar(select(probe.c.value)) == malicious
        role = (
            await session.execute(
                text(
                    "SELECT rolsuper, rolcreatedb, rolcreaterole FROM pg_roles WHERE rolname = current_user"
                )
            )
        ).one()
        assert tuple(role) == (False, False, False)


async def test_failed_use_case_rolls_back(database: Database) -> None:
    async with database.session() as session:
        with pytest.raises(ValueError, match="test use case failed"):
            async with transaction(session):
                await session.execute(probe.insert().values(id=1))
                raise ValueError("test use case failed")
        assert not session.in_transaction()
        async with transaction(session):
            assert await session.scalar(select(func.count()).select_from(probe)) == 0
    assert await count_rows(database) == 0


async def test_unique_violation_rolls_back_partial_work(database: Database) -> None:
    async with database.session() as session:
        with pytest.raises(IntegrityError):
            async with transaction(session):
                await session.execute(probe.insert().values(id=1))
                await session.execute(probe.insert().values(id=1))
    assert await count_rows(database) == 0


async def test_session_exit_never_silently_commits(database: Database) -> None:
    async with database.session() as session:
        await session.execute(probe.insert().values(id=1))
    assert await count_rows(database) == 0


async def test_nested_transaction_ownership_is_rejected(database: Database) -> None:
    async with database.session() as session:
        with pytest.raises(RuntimeError, match="fresh transaction"):
            async with transaction(session):
                await session.execute(probe.insert().values(id=1))
                async with transaction(session):
                    pytest.fail("Implicit nested ownership was accepted")
    assert await count_rows(database) == 0


async def test_cancellation_rolls_back_and_releases_connection(database: Database) -> None:
    entered = asyncio.Event()

    async def use_case() -> None:
        async with database.session() as session:
            async with transaction(session):
                await session.execute(probe.insert().values(id=1))
                entered.set()
                await asyncio.Event().wait()

    task = asyncio.create_task(use_case())
    try:
        async with asyncio.timeout(5):
            await entered.wait()
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        assert await count_rows(database) == 0
        assert await database.check_ready()
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def test_concurrent_tasks_have_distinct_sessions(database: Database) -> None:
    barrier = asyncio.Barrier(2)
    sessions = []

    async def use_case(identifier: int) -> None:
        async with database.session() as session:
            sessions.append(session)
            async with transaction(session):
                await session.execute(probe.insert().values(id=identifier))
                await barrier.wait()

    async with asyncio.timeout(5):
        await asyncio.gather(use_case(1), use_case(2))
    assert sessions[0] is not sessions[1]
    assert await count_rows(database) == 2


async def test_concurrent_requests_have_distinct_sessions(db_settings: Settings) -> None:
    app = create_app(db_settings)
    barrier = asyncio.Barrier(2)
    sessions = []

    async def endpoint(session: Annotated[AsyncSession, Depends(get_session)]) -> dict[str, bool]:
        sessions.append(session)
        assert await session.scalar(text("SELECT 1")) == 1
        await barrier.wait()
        return {"ok": True}

    app.add_api_route("/test/session", endpoint)
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as client:
            async with asyncio.timeout(5):
                responses = await asyncio.gather(
                    client.get("/test/session"), client.get("/test/session")
                )
            assert all(response.status_code == 200 for response in responses)
    assert sessions[0] is not sessions[1]
    assert all(not session.in_transaction() for session in sessions)


async def test_pool_is_bounded_and_recovers_after_exhaustion(
    database: Database, db_settings: Settings
) -> None:
    sessions = [
        database.session_factory()
        for _ in range(db_settings.DATABASE_POOL_SIZE + db_settings.DATABASE_MAX_OVERFLOW)
    ]
    try:
        for session in sessions:
            await session.scalar(text("SELECT 1"))
        async with database.session() as extra:
            with pytest.raises(PoolTimeout):
                await extra.scalar(text("SELECT 1"))
        assert await database.check_ready() is False
    finally:
        for session in sessions:
            await session.close()
    assert await database.check_ready()


@pytest.mark.parametrize("failure", [None, "unavailable", "expired_credentials"])
async def test_real_database_readiness_and_independent_liveness(
    settings_values: dict[str, Any], postgres_url: URL, failure: str | None
) -> None:
    with socket.socket() as unavailable:
        unavailable.bind(("127.0.0.1", 0))  # Reserved but not listening: deterministic refusal.
        if failure == "unavailable":
            postgres_url = postgres_url.set(port=unavailable.getsockname()[1])
        elif failure == "expired_credentials":
            postgres_url = postgres_url.set(password="p03-rejected-credential-canary")
        settings = Settings(
            _env_file=None,
            **(
                settings_values
                | {"DATABASE_URL": postgres_url.render_as_string(hide_password=False)}
            ),
        )
        app = create_app(settings)
        async with app.router.lifespan_context(app):
            async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as client:
                assert (await client.get("/health/live")).status_code == 200
                async with asyncio.timeout(settings.DATABASE_READINESS_TIMEOUT_SECONDS + 2):
                    ready = await client.get("/health/ready")
                assert ready.status_code == (503 if failure else 200)
                assert "p03-rejected-credential-canary" not in ready.text
                if failure:
                    assert ready.json()["error"]["code"] == "DEPENDENCY_UNAVAILABLE"
                assert (await client.get("/health/live")).status_code == 200
        assert not hasattr(app.state, "database")


async def test_database_readiness_metrics(database: Database) -> None:
    labels = {"outcome": "success"}
    before = REGISTRY.get_sample_value("marketing_ai_database_checks_total", labels) or 0
    assert await database.check_ready()
    assert REGISTRY.get_sample_value("marketing_ai_database_checks_total", labels) == before + 1
    assert REGISTRY.get_sample_value("marketing_ai_database_check_duration_seconds_count", labels)
