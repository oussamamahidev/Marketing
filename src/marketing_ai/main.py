"""Minimal ASGI application factory for the repository foundation.

PURPOSE: Provide a constructible FastAPI entrypoint and non-sensitive bootstrap health wiring.
RESPONSIBILITY: Owns only P01 application construction; it must not implement business routes, configuration, authentication, or integrations.
DEPENDENCIES: FastAPI and package metadata.
USED BY: Uvicorn, Docker, local development, and import smoke tests.
TESTED BY: tests/unit/test_imports.py.
"""

from __future__ import annotations

from fastapi import FastAPI

from marketing_ai import __version__

APP_TITLE = "Maroc Affiliate AI Marketing Assistant"


def create_app() -> FastAPI:
    """Create the minimal application without external dependency side effects."""
    application = FastAPI(
        title=APP_TITLE,
        version=__version__,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    @application.get("/", include_in_schema=False)
    async def bootstrap() -> dict[str, str]:
        return {"service": "marketing-ai", "status": "bootstrap"}

    @application.get("/health", include_in_schema=False)
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return application


app = create_app()
