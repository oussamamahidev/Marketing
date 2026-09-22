"""Authorization decisions and seller-scoped lookup conventions.

The application layer owns permission checks and passes a verified seller ID to
repositories. Repository implementations must expose seller-scoped operations;
they must never accept an unscoped seller-owned resource lookup.
"""

from collections.abc import Awaitable
from typing import Protocol, TypeVar
from uuid import UUID

from marketing_ai.core.errors import ApplicationError, ErrorCode
from marketing_ai.domain.identity.permissions import Permission
from marketing_ai.domain.identity.principal import Principal, SellerContext

ResourceT = TypeVar("ResourceT", covariant=True)


class SellerScopedLookup(Protocol[ResourceT]):
    """Port contract for a repository lookup that cannot omit its tenant scope."""

    def get_for_seller(
        self, *, seller_id: UUID, resource_id: UUID
    ) -> Awaitable[ResourceT | None]: ...


def authorize(principal: Principal, permission: Permission) -> Principal:
    """Require an explicit effective permission; no implicit admin bypass exists."""
    if not principal.has_permission(permission):
        raise ApplicationError(ErrorCode.FORBIDDEN)
    return principal


def seller_context(principal: Principal) -> SellerContext:
    return SellerContext.from_principal(principal)


async def get_owned_resource(
    repository: SellerScopedLookup[ResourceT], *, context: SellerContext, resource_id: UUID
) -> ResourceT:
    """Load only within the verified tenant and hide cross-tenant existence."""
    resource = await repository.get_for_seller(seller_id=context.seller_id, resource_id=resource_id)
    if resource is None:
        raise ApplicationError(ErrorCode.RESOURCE_NOT_FOUND)
    return resource
