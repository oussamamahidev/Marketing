"""Foundation smoke tests for package imports and minimal ASGI wiring.

PURPOSE: Prove the src-layout package and P01 app factory work without external services.
RESPONSIBILITY: Tests import and bootstrap behavior only; it does not test future business routes or integrations.
DEPENDENCIES: httpx ASGI transport and the marketing_ai package.
USED BY: P01 quality checks and future regression runs.
TESTED BY: pytest.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
from fastapi import FastAPI

import marketing_ai
from marketing_ai.main import APP_TITLE, app, create_app

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def test_package_import_exposes_version() -> None:
    assert marketing_ai.__version__ == "0.1.0"


def test_binding_context_files_exist_at_repository_root() -> None:
    required_files = {
        "PROJECT_CONTEXT.md": "# PROJECT_CONTEXT.md",
        "BUSINESS_CONSTANTS.md": "# BUSINESS_CONSTANTS.md",
    }

    for filename, expected_heading in required_files.items():
        document_path = REPOSITORY_ROOT / filename
        assert document_path.is_file(), filename
        document = document_path.read_text(encoding="utf-8")
        assert document.startswith(expected_heading), filename


def test_app_factory_constructs_fastapi_without_external_dependencies() -> None:
    application = create_app()

    assert isinstance(application, FastAPI)
    assert application.title == APP_TITLE
    assert application.version == marketing_ai.__version__


def test_bootstrap_and_health_endpoints_are_safe() -> None:
    async def request_endpoints() -> tuple[httpx.Response, httpx.Response]:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.get("/"), await client.get("/health")

    bootstrap_response, health_response = asyncio.run(request_endpoints())

    assert bootstrap_response.status_code == 200
    assert bootstrap_response.json() == {
        "service": "marketing-ai",
        "status": "bootstrap",
    }
    assert health_response.status_code == 200
    assert health_response.json() == {"status": "ok"}
