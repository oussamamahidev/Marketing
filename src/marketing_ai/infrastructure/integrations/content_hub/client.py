"""Seller-scoped read-only Content Hub adapter.

PURPOSE: retrieve selected creative metadata from trusted storage references.
RESPONSIBILITY: map one scoped read and enforce approved media hosts; never fetch or mutate media.
DEPENDENCIES: shared read transport and Content Hub schema.
USED BY: ProductAdvertisingContextService.
TESTED BY: tests/contract/internal/test_content_hub_contract.py.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import httpx2

from marketing_ai.core.errors import ApplicationError, ErrorCode
from marketing_ai.infrastructure.integrations.common import (
    ReadOnlyInternalClient,
    ensure_seller_scope,
    read_client_config_from_settings,
)
from marketing_ai.infrastructure.integrations.content_hub.schemas import CreativeMetadata

if TYPE_CHECKING:
    from marketing_ai.core.config import Settings


class ContentHubClient:
    @classmethod
    def from_settings(
        cls, *, settings: Settings, http_client: httpx2.AsyncClient
    ) -> "ContentHubClient":
        return cls(
            ReadOnlyInternalClient(
                service="content_hub",
                config=read_client_config_from_settings(
                    settings=settings, base_url=settings.CONTENT_HUB_SERVICE_BASE_URL
                ),
                http_client=http_client,
            ),
            approved_storage_hosts=frozenset(settings.CONTENT_HUB_APPROVED_STORAGE_HOSTS),
        )

    def __init__(
        self, transport: ReadOnlyInternalClient, *, approved_storage_hosts: frozenset[str]
    ) -> None:
        if not approved_storage_hosts:
            raise ValueError("Content Hub requires approved storage hosts")
        self._transport = transport
        self._approved_storage_hosts = frozenset(host.lower() for host in approved_storage_hosts)

    async def get_creative(self, *, seller_id: UUID, creative_id: UUID) -> CreativeMetadata:
        payload = await self._transport.get_json(
            seller_id=seller_id, path=f"/v1/sellers/{seller_id}/creatives/{creative_id}"
        )
        creative = CreativeMetadata.from_payload(
            payload, approved_storage_hosts=self._approved_storage_hosts
        )
        ensure_seller_scope(requested_seller_id=seller_id, resource_seller_id=creative.seller_id)
        if creative.creative_id != creative_id:
            raise ApplicationError(ErrorCode.UPSTREAM_INVALID_RESPONSE)
        return creative
