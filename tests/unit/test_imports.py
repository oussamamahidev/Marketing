"""Prove installed-package imports and minimal startup without service access."""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx2 import AsyncClient

from marketing_ai.core.config import Settings
from marketing_ai.main import create_app


def test_package_imports_outside_repository(tmp_path: Path) -> None:
    # Isolated mode ignores PYTHONPATH and user site packages: installation matters.
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            "import marketing_ai; from marketing_ai.main import create_app",
        ],
        cwd=tmp_path,
        env={key: value for key, value in os.environ.items() if key != "PYTHONPATH"},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == ""


def test_factory_creates_independent_apps(app: FastAPI, settings: Settings) -> None:
    other = create_app(settings)
    app.state.test_marker = "isolated"
    assert other is not app
    assert not hasattr(other.state, "test_marker")


@pytest.mark.anyio
async def test_startup_and_openapi_have_no_business_routes(client: AsyncClient) -> None:
    response = await client.get("/openapi.json")
    assert response.status_code == 200
    assert set(response.json()["paths"]) == {"/health/live", "/health/ready"}
    assert (await client.get("/docs")).status_code == 200
    assert (await client.get("/redoc")).status_code == 200
    assert (await client.get("/")).status_code == 404
    assert (await client.get("/health")).status_code == 404


@pytest.mark.parametrize("dependency_environment", [False, True])
def test_import_does_not_connect_or_require_settings(
    tmp_path: Path, dependency_environment: bool
) -> None:
    environment = {
        key: value
        for key, value in os.environ.items()
        if key not in {"PYTHONPATH", "DATABASE_URL", "REDIS_URL", "POSTGRES_PASSWORD"}
    }
    if dependency_environment:
        environment.update(DATABASE_URL="invalid://unavailable", REDIS_URL="invalid://unavailable")
    (tmp_path / ".env").write_text("THIS IS NOT VALID APPLICATION CONFIGURATION\n")
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            """
import socket
def reject_connection(*args, **kwargs):
    raise AssertionError('P01 import/factory attempted external I/O')
socket.create_connection = reject_connection
socket.socket.connect = reject_connection
socket.socket.connect_ex = reject_connection
import marketing_ai
from marketing_ai.main import create_app
""",
        ],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == ""


def test_only_framework_docs_and_health_routes_exist(app: FastAPI) -> None:
    from starlette.routing import Route

    # Included API routers may be stored lazily; OpenAPI is their public contract.
    assert {route.path for route in app.routes if isinstance(route, Route)} == {
        "/openapi.json",
        "/docs",
        "/docs/oauth2-redirect",
        "/redoc",
    }
    assert set(app.openapi()["paths"]) == {"/health/live", "/health/ready"}
    assert app.debug is False


@pytest.mark.anyio
@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/api/v1/campaigns/foreign-seller-id"),
        ("POST", "/api/v1/campaigns"),
        ("GET", "/admin"),
    ],
)
async def test_absent_business_routes_do_not_echo_untrusted_input(
    client: AsyncClient, method: str, path: str
) -> None:
    sentinel = "p01-untrusted-input-canary"
    response = await client.request(
        method, path, content=b"{malformed-json", headers={"Authorization": sentinel}
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "RESOURCE_NOT_FOUND"
    assert sentinel not in response.text
