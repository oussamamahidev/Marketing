"""Database configuration and assembly contracts without external I/O."""

from pathlib import Path
from typing import Any

import pytest
from alembic.config import Config
from fastapi import Depends, FastAPI
from httpx2 import ASGITransport, AsyncClient
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from marketing_ai.api.dependencies import get_session
from marketing_ai.core.config import Settings
from marketing_ai.infrastructure.database.base import Base
from marketing_ai.infrastructure.database.migrations import single_head


@pytest.mark.parametrize(
    "url",
    [
        "",
        "not-a-url",
        "sqlite:///test.db",
        "postgresql://u:p@localhost/db",
        "postgresql+psycopg://u@localhost/db",
        "postgresql+psycopg://u:p@localhost:invalid/db",
    ],
)
def test_database_url_is_required_valid_and_secret(
    settings_values: dict[str, Any], url: str
) -> None:
    with pytest.raises(ValidationError) as caught:
        Settings(_env_file=None, **(settings_values | {"DATABASE_URL": url}))
    assert "input_value=" not in str(caught.value)


@pytest.mark.parametrize(
    "field,value",
    [
        ("DATABASE_POOL_SIZE", "0"),
        ("DATABASE_MAX_OVERFLOW", "-1"),
        ("DATABASE_POOL_TIMEOUT_SECONDS", "0"),
        ("DATABASE_CONNECT_TIMEOUT_SECONDS", "0"),
        ("DATABASE_READINESS_TIMEOUT_SECONDS", "0"),
    ],
)
def test_database_limits_cannot_be_unbounded(
    settings_values: dict[str, Any], field: str, value: str
) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **(settings_values | {field: value}))


def test_foundation_metadata_has_no_business_tables_and_single_head() -> None:
    assert not Base.metadata.tables
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    assert single_head(config) == "0001_persistence_foundation"


@pytest.mark.anyio
async def test_readiness_fails_closed_if_lifespan_is_disabled(app: FastAPI) -> None:
    async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as client:
        assert (await client.get("/health/live")).status_code == 200
        assert (await client.get("/health/ready")).status_code == 503


@pytest.mark.anyio
async def test_session_dependency_fails_closed_if_lifespan_is_disabled(app: FastAPI) -> None:
    async def endpoint(_: AsyncSession = Depends(get_session)) -> dict[str, bool]:
        return {"unexpected": True}

    app.add_api_route("/test/session-without-lifespan", endpoint)
    async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as client:
        response = await client.get("/test/session-without-lifespan")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "DEPENDENCY_UNAVAILABLE"
