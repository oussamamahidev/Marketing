"""Seller-scoped read-only Inventory adapter.

PURPOSE: retrieve the inventory summary needed for advertising eligibility.
RESPONSIBILITY: map one scoped read; no stock mutation or raw payload exposure.
DEPENDENCIES: shared read transport and inventory schema.
USED BY: ProductAdvertisingContextService.
TESTED BY: tests/contract/internal/test_inventory_contract.py.
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
from marketing_ai.infrastructure.integrations.inventory.schemas import InventorySummary

if TYPE_CHECKING:
    from marketing_ai.core.config import Settings


class InventoryClient:
    @classmethod
    def from_settings(
        cls, *, settings: Settings, http_client: httpx2.AsyncClient
    ) -> "InventoryClient":
        return cls(
            ReadOnlyInternalClient(
                service="inventory",
                config=read_client_config_from_settings(
                    settings=settings, base_url=settings.INVENTORY_SERVICE_BASE_URL
                ),
                http_client=http_client,
            )
        )

    def __init__(self, transport: ReadOnlyInternalClient) -> None:
        self._transport = transport

    async def get_summary(self, *, seller_id: UUID, product_id: UUID) -> InventorySummary:
        payload = await self._transport.get_json(
            seller_id=seller_id,
            path=f"/v1/sellers/{seller_id}/products/{product_id}/inventory-summary",
        )
        summary = InventorySummary.from_payload(payload)
        ensure_seller_scope(requested_seller_id=seller_id, resource_seller_id=summary.seller_id)
        if summary.product_id != product_id:
            raise ApplicationError(ErrorCode.UPSTREAM_INVALID_RESPONSE)
        return summary
