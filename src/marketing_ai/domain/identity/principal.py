"""Framework-independent authenticated identity and seller context.

Only a trusted identity adapter may construct this value from external claims.
Application use cases consume the principal or its seller context; no raw token
or web framework object crosses into the domain.
"""

from dataclasses import dataclass
from uuid import UUID

from marketing_ai.domain.identity.permissions import Permission, Role, permissions_for_roles


@dataclass(frozen=True)
class Principal:
    user_id: UUID
    seller_id: UUID
    roles: frozenset[Role]
    permissions: frozenset[Permission]
    is_platform_admin: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.user_id, UUID) or not isinstance(self.seller_id, UUID):
            raise ValueError("Principal identifiers must be UUIDs")
        if not isinstance(self.is_platform_admin, bool):
            raise ValueError("Platform-admin status must be a boolean")
        if any(not isinstance(role, Role) for role in self.roles):
            raise ValueError("Principal roles must use the approved role vocabulary")
        if any(not isinstance(permission, Permission) for permission in self.permissions):
            raise ValueError("Principal permissions must use the approved permission vocabulary")
        object.__setattr__(
            self,
            "permissions",
            frozenset(self.permissions | permissions_for_roles(self.roles)),
        )

    def has_permission(self, permission: Permission) -> bool:
        """A platform-admin flag is not an implicit cross-tenant permission bypass."""
        if not isinstance(permission, Permission):
            raise ValueError("Permission checks require an approved permission")
        return permission in self.permissions


@dataclass(frozen=True)
class SellerContext:
    """The verified tenant boundary that every seller-owned query receives."""

    seller_id: UUID

    def __post_init__(self) -> None:
        if not isinstance(self.seller_id, UUID):
            raise ValueError("Seller context identifier must be a UUID")

    @classmethod
    def from_principal(cls, principal: Principal) -> "SellerContext":
        if not isinstance(principal, Principal):
            raise ValueError("Seller context requires an authenticated principal")
        return cls(seller_id=principal.seller_id)
