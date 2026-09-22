"""Compose the current HTTP surface without adding business routes."""

from fastapi import APIRouter

from marketing_ai.api.v1.health import router as health_router

router = APIRouter()
router.include_router(health_router)
