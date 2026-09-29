"""Compose health and tenant-scoped lifecycle routes."""

from fastapi import APIRouter

from marketing_ai.api.v1.health import router as health_router
from marketing_ai.api.v1.meta_connections import router as meta_connections_router

router = APIRouter()
router.include_router(health_router)
router.include_router(meta_connections_router)
