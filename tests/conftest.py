"""Isolated application fixtures; no database, network or credentials required."""

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from httpx2 import ASGITransport, AsyncClient

from marketing_ai.core.config import Settings
from marketing_ai.main import create_app

pytest_plugins = ("tests.support.postgres",)


@pytest.fixture
def database_test_values() -> dict[str, str]:
    # Synthetic harness settings, not approved deployment defaults.
    return {
        "DATABASE_URL": "postgresql+psycopg://test:test@127.0.0.1:1/test",
        "DATABASE_POOL_SIZE": "2",
        "DATABASE_MAX_OVERFLOW": "1",
        "DATABASE_POOL_TIMEOUT_SECONDS": "1",
        "DATABASE_CONNECT_TIMEOUT_SECONDS": "1",
        "DATABASE_READINESS_TIMEOUT_SECONDS": "1",
    }


@pytest.fixture
def identity_test_values() -> dict[str, str]:
    # Synthetic harness identity only; never a deployed signing credential.
    return {
        "IDENTITY_JWT_ISSUER": "https://identity.test.maroc-affiliate",
        "IDENTITY_JWT_AUDIENCE": "marketing-ai-test",
        "IDENTITY_JWT_HS256_SECRET": "p04-test-signing-secret",
        "META_OAUTH_STATE_SIGNING_SECRET": "p07-test-state-secret",
        "META_OAUTH_STATE_TTL_SECONDS": "60",
    }


@pytest.fixture
def settings_values(
    database_test_values: dict[str, str], identity_test_values: dict[str, str]
) -> dict[str, Any]:
    path = Path(__file__).resolve().parents[1] / ".env.example"
    values = dict(
        line.split("=", 1)
        for line in path.read_text().splitlines()
        if line and not line.startswith("#")
    )
    return (
        {key: value for key, value in values.items() if key in Settings.model_fields}
        | database_test_values
        | identity_test_values
        | {"ENVIRONMENT": "test"}
    )


@pytest.fixture
def settings(settings_values: dict[str, Any]) -> Settings:
    return Settings(_env_file=None, **settings_values)


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    return create_app(settings)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    # ASGITransport does not drive lifespan; enter it explicitly for startup/shutdown.
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as test_client:
            yield test_client
