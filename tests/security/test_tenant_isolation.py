"""Tenant-bound lookup tests; cross-seller references are indistinguishable from missing."""

from uuid import UUID

import pytest

from marketing_ai.application.identity.authorization import get_owned_resource, seller_context
from marketing_ai.core.errors import ApplicationError, ErrorCode
from marketing_ai.domain.identity.permissions import Role
from marketing_ai.domain.identity.principal import Principal

USER_A = UUID("00000000-0000-0000-0000-000000000001")
SELLER_A = UUID("00000000-0000-0000-0000-000000000010")
SELLER_B = UUID("00000000-0000-0000-0000-000000000020")
FOREIGN_RESOURCE = UUID("00000000-0000-0000-0000-000000000100")
MISSING_RESOURCE = UUID("00000000-0000-0000-0000-000000000101")


def caller_a(*, platform_admin: bool = False) -> Principal:
    return Principal(
        user_id=USER_A,
        seller_id=SELLER_A,
        roles=frozenset({Role.ADS_ADMIN}),
        permissions=frozenset(),
        is_platform_admin=platform_admin,
    )


@pytest.mark.anyio
@pytest.mark.parametrize("resource_id", [FOREIGN_RESOURCE, MISSING_RESOURCE])
async def test_cross_seller_and_missing_references_fail_as_same_scoped_not_found(
    resource_id: UUID,
) -> None:
    calls: list[tuple[UUID, UUID]] = []

    class TenantRepository:
        async def get_for_seller(self, *, seller_id: UUID, resource_id: UUID) -> str | None:
            calls.append((seller_id, resource_id))
            # A repository query is equivalent to WHERE seller_id = :seller_id AND id = :id.
            return None if seller_id != SELLER_B else "foreign resource"

    with pytest.raises(ApplicationError) as caught:
        await get_owned_resource(
            TenantRepository(), context=seller_context(caller_a()), resource_id=resource_id
        )
    assert caught.value.code is ErrorCode.RESOURCE_NOT_FOUND
    assert calls == [(SELLER_A, resource_id)]


@pytest.mark.anyio
async def test_platform_admin_flag_does_not_implicitly_cross_tenant_boundary() -> None:
    class TenantRepository:
        async def get_for_seller(self, *, seller_id: UUID, resource_id: UUID) -> str | None:
            return "foreign resource" if seller_id == SELLER_B else None

    with pytest.raises(ApplicationError) as caught:
        await get_owned_resource(
            TenantRepository(),
            context=seller_context(caller_a(platform_admin=True)),
            resource_id=FOREIGN_RESOURCE,
        )
    assert caught.value.code is ErrorCode.RESOURCE_NOT_FOUND
