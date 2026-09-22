"""Compose validated runtime settings, logging, middleware, errors and health."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from marketing_ai.api.dependencies import ReadinessProbe
from marketing_ai.api.error_handlers import register_error_handlers
from marketing_ai.api.middleware import RequestContextMiddleware
from marketing_ai.api.v1.router import router
from marketing_ai.core.config import Settings, load_settings
from marketing_ai.core.logging import configure_logging
from marketing_ai.infrastructure.database.session import Database


def create_app(
    settings: Settings | None = None,
    *,
    readiness_probes: tuple[ReadinessProbe, ...] = (),
) -> FastAPI:
    configuration = settings if settings is not None else load_settings()
    if "postgresql" in {probe.name for probe in readiness_probes} or len(
        {probe.name for probe in readiness_probes}
    ) != len(readiness_probes):
        raise ValueError("Readiness probe names must be unique")

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        configure_logging(environment=configuration.ENVIRONMENT, level=configuration.LOG_LEVEL)
        logger = logging.getLogger(__name__)
        logger.info("service_started")
        database = Database(configuration)
        app.state.database = database
        app.state.readiness_probes = (
            ReadinessProbe(
                "postgresql", database.check_ready, configuration.DATABASE_READINESS_TIMEOUT_SECONDS
            ),
            *readiness_probes,
        )
        try:
            yield
        finally:
            try:
                await database.close()
            finally:
                del app.state.database
                logger.info("service_stopped")

    app = FastAPI(title="Maroc Affiliate AI Marketing Assistant", lifespan=lifespan)
    app.state.settings = configuration
    app.state.readiness_probes = readiness_probes
    app.add_middleware(RequestContextMiddleware)
    register_error_handlers(app)
    app.include_router(router)
    return app
