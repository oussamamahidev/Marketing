"""P06 Catalog read-adapter contract tests.

PURPOSE: prove seller-scoped mapping and safe transport failure translation.
RESPONSIBILITY: exercise adapter contracts without a real platform service.
DEPENDENCIES: httpx2 mock transport and P06 adapter interfaces.
USED BY: P06 regression suite.
TESTED BY: this module.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import httpx2
import pytest

from marketing_ai.application.context.product_context import ProductAdvertisingContextService
from marketing_ai.core.config import ConfigurationError, Settings
from marketing_ai.core.errors import ApplicationError, ErrorCode
from marketing_ai.infrastructure.integrations.catalog.client import CatalogClient
from marketing_ai.infrastructure.integrations.catalog.schemas import CatalogProduct
from marketing_ai.infrastructure.integrations.common import (
    InternalReadClientConfig,
    ReadOnlyInternalClient,
)
from marketing_ai.infrastructure.integrations.content_hub.schemas import CreativeMetadata
from marketing_ai.infrastructure.integrations.inventory.schemas import InventorySummary
from marketing_ai.infrastructure.integrations.orders.schemas import OrderOutcomeSummary


def config() -> InternalReadClientConfig:
    return InternalReadClientConfig(
        base_url="https://catalog.internal.test",
        service_identity="marketing-ai",
        timeout_seconds=1,
        max_retries=1,
    )


def product_payload(seller_id: UUID, product_id: UUID) -> dict[str, object]:
    return {
        "seller_id": str(seller_id),
        "product_id": str(product_id),
        "name": "Product",
        "price_centimes": 1,
        "gross_margin_pct": "30",
    }


@pytest.mark.anyio
async def test_catalog_sends_service_and_seller_identity_and_hides_foreign_product() -> None:
    seller_id, product_id = uuid4(), uuid4()

    async def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.headers["X-Seller-ID"] == str(seller_id)
        assert request.headers["X-Service-Identity"] == "marketing-ai"
        assert request.url.path.endswith(f"/products/{product_id}")
        return httpx2.Response(200, json=product_payload(seller_id, product_id))

    async with httpx2.AsyncClient(transport=httpx2.MockTransport(handler)) as http_client:
        catalog = CatalogClient(
            ReadOnlyInternalClient(service="catalog", config=config(), http_client=http_client)
        )
        assert (
            await catalog.get_product(seller_id=seller_id, product_id=product_id)
        ).name == "Product"

    foreign_seller = uuid4()
    async with httpx2.AsyncClient(
        transport=httpx2.MockTransport(
            lambda request: httpx2.Response(200, json=product_payload(foreign_seller, product_id))
        )
    ) as http_client:
        catalog = CatalogClient(
            ReadOnlyInternalClient(service="catalog", config=config(), http_client=http_client)
        )
        with pytest.raises(ApplicationError) as raised:
            await catalog.get_product(seller_id=seller_id, product_id=product_id)
    assert raised.value.code == ErrorCode.RESOURCE_NOT_FOUND


@pytest.mark.anyio
async def test_catalog_distinguishes_timeout_from_malformed_response() -> None:
    seller_id, product_id = uuid4(), uuid4()

    async def timeout(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ReadTimeout("test timeout", request=request)

    async with httpx2.AsyncClient(transport=httpx2.MockTransport(timeout)) as http_client:
        catalog = CatalogClient(
            ReadOnlyInternalClient(service="catalog", config=config(), http_client=http_client)
        )
        with pytest.raises(ApplicationError) as timeout_error:
            await catalog.get_product(seller_id=seller_id, product_id=product_id)
    assert timeout_error.value.code == ErrorCode.UPSTREAM_TIMEOUT

    async with httpx2.AsyncClient(
        transport=httpx2.MockTransport(lambda request: httpx2.Response(200, json=["raw"]))
    ) as http_client:
        catalog = CatalogClient(
            ReadOnlyInternalClient(service="catalog", config=config(), http_client=http_client)
        )
        with pytest.raises(ApplicationError) as malformed_error:
            await catalog.get_product(seller_id=seller_id, product_id=product_id)
    assert malformed_error.value.code == ErrorCode.UPSTREAM_INVALID_RESPONSE


@pytest.mark.anyio
async def test_context_aggregates_only_typed_seller_scoped_facts() -> None:
    seller_id, product_id, creative_id = uuid4(), uuid4(), uuid4()
    product = CatalogProduct.from_payload(product_payload(seller_id, product_id))
    inventory = InventorySummary(product_id, seller_id, available_units=1, warehouse_count=1)
    outcomes = OrderOutcomeSummary(
        product_id,
        seller_id,
        orders_in_sample=0,
        cancellation_rate_pct=Decimal("0"),
        return_rate_pct=Decimal("0"),
    )
    creative = CreativeMetadata(
        creative_id, seller_id, "Creative", "https://media.test/a.jpg", "image"
    )

    class Readers:
        async def get_product(self, *, seller_id: UUID, product_id: UUID) -> CatalogProduct:
            return product

        async def get_summary(self, *, seller_id: UUID, product_id: UUID) -> InventorySummary:
            return inventory

        async def get_outcome_summary(
            self, *, seller_id: UUID, product_id: UUID
        ) -> OrderOutcomeSummary:
            return outcomes

        async def get_creative(self, *, seller_id: UUID, creative_id: UUID) -> CreativeMetadata:
            return creative

    readers = Readers()
    context = await ProductAdvertisingContextService(
        catalog=readers, inventory=readers, orders=readers, content_hub=readers
    ).get_context(seller_id=seller_id, product_id=product_id, creative_id=creative_id)
    assert context.product is product and context.creative is creative


@pytest.mark.anyio
async def test_client_settings_factory_requires_complete_typed_configuration(
    settings_values: dict[str, Any],
) -> None:
    async with httpx2.AsyncClient() as http_client:
        with pytest.raises(ConfigurationError):
            CatalogClient.from_settings(
                settings=Settings(_env_file=None, **settings_values), http_client=http_client
            )

    configured = Settings(
        _env_file=None,
        **(
            settings_values
            | {
                "CATALOG_SERVICE_BASE_URL": "https://catalog.internal.test",
                "INTERNAL_SERVICE_IDENTITY": "synthetic-service-identity",
                "INTERNAL_READ_TIMEOUT_SECONDS": "1",
                "INTERNAL_READ_MAX_RETRIES": "0",
            }
        ),
    )
    async with httpx2.AsyncClient() as http_client:
        client = CatalogClient.from_settings(settings=configured, http_client=http_client)
        assert isinstance(client, CatalogClient)
