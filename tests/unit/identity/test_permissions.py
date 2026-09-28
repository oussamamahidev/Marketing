"""Domain and application authorization tests; no HTTP or signed token parsing."""

from uuid import UUID

import pytest

from marketing_ai.application.identity.authorization import (
    authorize,
    get_owned_resource,
    seller_context,
)
from marketing_ai.core.errors import ApplicationError, ErrorCode
from marketing_ai.domain.identity.permissions import Permission, Role, permissions_for_roles
from marketing_ai.domain.identity.principal import Principal

USER_ID = UUID("00000000-0000-0000-0000-000000000001")
SELLER_ID = UUID("00000000-0000-0000-0000-000000000010")


def principal(*roles: Role, platform_admin: bool = False) -> Principal:
    return Principal(
        user_id=USER_ID,
        seller_id=SELLER_ID,
        roles=frozenset(roles),
        permissions=frozenset(),
        is_platform_admin=platform_admin,
    )


@pytest.mark.parametrize(
    ("role", "expected"),
    [
        (Role.ADS_VIEWER, {Permission.ADS_READ}),
        (Role.ADS_MANAGER, {Permission.ADS_READ, Permission.ADS_MANAGE}),
        (Role.ADS_APPROVER, {Permission.ADS_READ, Permission.ADS_APPROVE}),
        (Role.ADS_ADMIN, set(Permission)),
    ],
)
def test_roles_map_to_explicit_permissions(role: Role, expected: set[Permission]) -> None:
    assert permissions_for_roles([role]) == frozenset(expected)
    assert principal(role).permissions == frozenset(expected)


def test_permission_denial_and_platform_admin_flag_do_not_create_implicit_bypass() -> None:
    caller = principal(platform_admin=True)
    assert caller.is_platform_admin is True
    with pytest.raises(ApplicationError) as caught:
        authorize(caller, Permission.ADS_MANAGE)
    assert caught.value.code is ErrorCode.FORBIDDEN


@pytest.mark.anyio
async def test_scoped_lookup_always_receives_verified_seller_id() -> None:
    calls: list[tuple[UUID, UUID]] = []
    resource_id = UUID("00000000-0000-0000-0000-000000000100")

    class Repository:
        async def get_for_seller(self, *, seller_id: UUID, resource_id: UUID) -> str | None:
            calls.append((seller_id, resource_id))
            return "owned"

    result = await get_owned_resource(
        Repository(), context=seller_context(principal(Role.ADS_VIEWER)), resource_id=resource_id
    )
    assert result == "owned"
    assert calls == [(SELLER_ID, resource_id)]


@pytest.mark.parametrize(
    ("role", "permission", "allowed"),
    [
        (Role.ADS_VIEWER, Permission.ADS_READ, True),
        (Role.ADS_VIEWER, Permission.ADS_MANAGE, False),
        (Role.ADS_MANAGER, Permission.ADS_MANAGE, True),
        (Role.ADS_MANAGER, Permission.ADS_APPROVE, False),
        (Role.ADS_APPROVER, Permission.ADS_APPROVE, True),
        (Role.ADS_APPROVER, Permission.ADS_ADMIN, False),
        (Role.ADS_ADMIN, Permission.ADS_ADMIN, True),
    ],
)
def test_permission_matrix(role: Role, permission: Permission, allowed: bool) -> None:
    caller = principal(role)
    if allowed:
        assert authorize(caller, permission) is caller
    else:
        with pytest.raises(ApplicationError) as caught:
            authorize(caller, permission)
        assert caught.value.code is ErrorCode.FORBIDDEN


@pytest.mark.parametrize(
    "changes",
    [
        {"user_id": "not-a-uuid"},
        {"seller_id": "not-a-uuid"},
        {"roles": frozenset({"ads_viewer"})},
        {"permissions": frozenset({"ads.read"})},
        {"is_platform_admin": 1},
    ],
)
def test_principal_rejects_invalid_identifiers_and_identity_values(
    changes: dict[str, object],
) -> None:
    values: dict[str, object] = {
        "user_id": USER_ID,
        "seller_id": SELLER_ID,
        "roles": frozenset(),
        "permissions": frozenset(),
        "is_platform_admin": False,
    }
    values.update(changes)
    with pytest.raises(ValueError):
        Principal(**values)  # type: ignore[arg-type]
