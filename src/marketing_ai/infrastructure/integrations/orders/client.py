"""Seller-scoped read-only Orders adapter.

PURPOSE: retrieve aggregate order outcomes for advertising risk evaluation.
RESPONSIBILITY: map one scoped summary read; no order/customer payload or mutation.
DEPENDENCIES: shared read transport and orders schema.
USED BY: ProductAdvertisingContextService.
TESTED BY: tests/contract/internal/test_orders_contract.py.
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
from marketing_ai.infrastructure.integrations.orders.schemas import OrderOutcomeSummary

if TYPE_CHECKING:
    from marketing_ai.core.config import Settings


class OrdersClient:
    @classmethod
    def from_settings(
        cls, *, settings: Settings, http_client: httpx2.AsyncClient
    ) -> "OrdersClient":
        return cls(
            ReadOnlyInternalClient(
                service="orders",
                config=read_client_config_from_settings(
                    settings=settings, base_url=settings.ORDERS_SERVICE_BASE_URL
                ),
                http_client=http_client,
            )
        )

    def __init__(self, transport: ReadOnlyInternalClient) -> None:
        self._transport = transport

    async def get_outcome_summary(
        self, *, seller_id: UUID, product_id: UUID
    ) -> OrderOutcomeSummary:
        payload = await self._transport.get_json(
            seller_id=seller_id,
            path=f"/v1/sellers/{seller_id}/products/{product_id}/order-outcomes",
        )
        summary = OrderOutcomeSummary.from_payload(payload)
        ensure_seller_scope(requested_seller_id=seller_id, resource_seller_id=summary.seller_id)
        if summary.product_id != product_id:
            raise ApplicationError(ErrorCode.UPSTREAM_INVALID_RESPONSE)
        return summary
