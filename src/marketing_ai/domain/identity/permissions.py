"""Authorization vocabulary and role-to-permission mapping.

This module owns stable advertising permissions. It has no HTTP, configuration,
or persistence dependency; identity adapters and application authorization use it.
"""

from collections.abc import Iterable
from enum import StrEnum


class Permission(StrEnum):
    ADS_READ = "ads.read"
    ADS_MANAGE = "ads.manage"
    ADS_APPROVE = "ads.approve"
    ADS_ADMIN = "ads.admin"


class Role(StrEnum):
    ADS_VIEWER = "ads_viewer"
    ADS_MANAGER = "ads_manager"
    ADS_APPROVER = "ads_approver"
    ADS_ADMIN = "ads_admin"


ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.ADS_VIEWER: frozenset({Permission.ADS_READ}),
    Role.ADS_MANAGER: frozenset({Permission.ADS_READ, Permission.ADS_MANAGE}),
    Role.ADS_APPROVER: frozenset({Permission.ADS_READ, Permission.ADS_APPROVE}),
    Role.ADS_ADMIN: frozenset(Permission),
}


def permissions_for_roles(roles: Iterable[Role]) -> frozenset[Permission]:
    """Return only the explicit permissions granted by the supplied roles."""
    permissions: set[Permission] = set()
    for role in roles:
        if not isinstance(role, Role):
            raise ValueError("Roles must use the approved role vocabulary")
        permissions.update(ROLE_PERMISSIONS[role])
    return frozenset(permissions)
