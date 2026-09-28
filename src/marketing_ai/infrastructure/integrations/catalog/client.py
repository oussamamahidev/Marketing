"""Seller-scoped read-only Catalog adapter.

PURPOSE: retrieve only product metadata required for advertising.
RESPONSIBILITY: map one scoped read to CatalogProduct; no product writes or raw payload exposure.
DEPENDENCIES: shared read transport and catalog schema.
USED BY: ProductAdvertisingContextService.
TESTED BY: tests/contract/internal/test_catalog_contract.py.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import httpx2

from marketing_ai.core.errors import ApplicationError, ErrorCode
from marketing_ai.infrastructure.integrations.catalog.schemas import CatalogProduct
from marketing_ai.infrastructure.integrations.common import (
    ReadOnlyInternalClient,
    ensure_seller_scope,
    read_client_config_from_settings,
)

if TYPE_CHECKING:
    from marketing_ai.core.config import Settings


class CatalogClient:
    @classmethod
    def from_settings(
        cls, *, settings: Settings, http_client: httpx2.AsyncClient
    ) -> "CatalogClient":
        return cls(
            ReadOnlyInternalClient(
                service="catalog",
                config=read_client_config_from_settings(
                    settings=settings, base_url=settings.CATALOG_SERVICE_BASE_URL
                ),
                http_client=http_client,
            )
        )

    def __init__(self, transport: ReadOnlyInternalClient) -> None:
        self._transport = transport

    async def get_product(self, *, seller_id: UUID, product_id: UUID) -> CatalogProduct:
        payload = await self._transport.get_json(
            seller_id=seller_id, path=f"/v1/sellers/{seller_id}/products/{product_id}"
        )
        product = CatalogProduct.from_payload(payload)
        ensure_seller_scope(requested_seller_id=seller_id, resource_seller_id=product.seller_id)
        if product.product_id != product_id:
            raise ApplicationError(ErrorCode.UPSTREAM_INVALID_RESPONSE)
        return product
