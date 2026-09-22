"""Dependency-free liveness; bounded readiness includes PostgreSQL from lifespan."""

import asyncio
import logging
from time import perf_counter
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from marketing_ai.api.dependencies import ReadinessProbe, get_readiness_probes
from marketing_ai.core.errors import ApplicationError, ErrorCode

router = APIRouter(prefix="/health", tags=["health"])
logger = logging.getLogger(__name__)


class HealthResponse(BaseModel):
    status: Literal["alive", "ready"]


@router.get("/live", response_model=HealthResponse)
async def live() -> HealthResponse:
    return HealthResponse(status="alive")


async def run_probe(probe: ReadinessProbe) -> bool:
    started = perf_counter()
    try:
        async with asyncio.timeout(probe.timeout_seconds):
            result = await probe.check()
            if type(result) is not bool or not result:
                raise ValueError("Invalid or unsuccessful readiness result")
    except Exception:
        logger.warning(
            "readiness_check_failed", extra={"duration_ms": (perf_counter() - started) * 1000}
        )
        return False
    logger.info(
        "readiness_check_complete", extra={"duration_ms": (perf_counter() - started) * 1000}
    )
    return True


@router.get("/ready", response_model=HealthResponse)
async def ready(
    probes: Annotated[tuple[ReadinessProbe, ...], Depends(get_readiness_probes)],
) -> HealthResponse:
    if not all(await asyncio.gather(*(run_probe(probe) for probe in probes))):
        raise ApplicationError(ErrorCode.DEPENDENCY_UNAVAILABLE)
    return HealthResponse(status="ready")
