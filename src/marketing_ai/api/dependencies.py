"""Typed request dependencies and bounded readiness extension point.

The composition root registers PostgreSQL and signed-identity verification.
Sessions are fresh for each request; identity dependencies return a validated
principal or canonical application errors, never raw bearer tokens.
"""

import math
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from marketing_ai.application.identity.authorization import authorize, seller_context
from marketing_ai.core.config import Settings
from marketing_ai.core.errors import ApplicationError, ErrorCode
from marketing_ai.core.security import (
    HmacSha256IdentityVerifier,
    IdentityVerificationError,
    IdentityVerifier,
)
from marketing_ai.domain.identity.permissions import Permission
from marketing_ai.domain.identity.principal import Principal, SellerContext
from marketing_ai.infrastructure.database.session import Database

bearer_identity = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class ReadinessProbe:
    name: str
    check: Callable[[], Awaitable[bool]]
    timeout_seconds: float

    def __post_init__(self) -> None:
        if not self.name or not self.name.isidentifier():
            raise ValueError("Readiness probe requires a valid identifier")
        if not math.isfinite(self.timeout_seconds) or self.timeout_seconds <= 0:
            raise ValueError("Readiness probe requires an explicit positive finite timeout")
        if not callable(self.check):
            raise ValueError("Readiness probe requires an async callable")


async def get_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


async def get_identity_verifier(
    settings: Annotated[Settings, Depends(get_settings)],
) -> IdentityVerifier:
    """Build the configured adapter; applications may override it in integration."""
    return HmacSha256IdentityVerifier(
        issuer=settings.IDENTITY_JWT_ISSUER,
        audience=settings.IDENTITY_JWT_AUDIENCE,
        signing_secret=settings.IDENTITY_JWT_HS256_SECRET.get_secret_value(),
    )


async def get_authenticated_principal(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_identity)],
    verifier: Annotated[IdentityVerifier, Depends(get_identity_verifier)],
) -> Principal:
    """Translate all bearer-token failures to the canonical unauthenticated error."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise ApplicationError(ErrorCode.UNAUTHENTICATED)
    try:
        return verifier.verify(credentials.credentials)
    except IdentityVerificationError, ValueError, TypeError:
        raise ApplicationError(ErrorCode.UNAUTHENTICATED) from None


def require_permission(
    permission: Permission,
) -> Callable[[Annotated[Principal, Depends(get_authenticated_principal)]], Awaitable[Principal]]:
    """Return a FastAPI dependency so handlers declare, rather than implement, policy."""
    if not isinstance(permission, Permission):
        raise ValueError("Required permission must use the approved permission vocabulary")

    async def dependency(
        principal: Annotated[Principal, Depends(get_authenticated_principal)],
    ) -> Principal:
        return authorize(principal, permission)

    return dependency


async def get_seller_context(
    principal: Annotated[Principal, Depends(get_authenticated_principal)],
) -> SellerContext:
    """Expose only the verified seller boundary to seller-owned use cases."""
    return seller_context(principal)


async def get_readiness_probes(request: Request) -> tuple[ReadinessProbe, ...]:
    if not hasattr(request.app.state, "database"):
        raise ApplicationError(ErrorCode.DEPENDENCY_UNAVAILABLE)
    probes: tuple[ReadinessProbe, ...] = request.app.state.readiness_probes
    return probes


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """Request owns session cleanup; application use case owns its transaction."""
    if not hasattr(request.app.state, "database"):
        raise ApplicationError(ErrorCode.DEPENDENCY_UNAVAILABLE)
    database: Database = request.app.state.database
    async with database.session() as session:
        yield session
