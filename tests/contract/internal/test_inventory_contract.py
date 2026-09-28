"""P06 Inventory read-adapter contract tests.

PURPOSE: prove typed warehouse-summary mapping and bounded dependency handling.
RESPONSIBILITY: exercise the read adapter without inventory writes or a real service.
DEPENDENCIES: httpx2 mock transport and P06 adapter interfaces.
USED BY: P06 regression suite.
TESTED BY: this module.
"""

from __future__ import annotations

from uuid import uuid4

import httpx2
import pytest

from marketing_ai.core.errors import ApplicationError, ErrorCode
from marketing_ai.infrastructure.integrations.common import (
    InternalReadClientConfig,
    ReadOnlyInternalClient,
)
from marketing_ai.infrastructure.integrations.inventory.client import InventoryClient


@pytest.mark.anyio
async def test_inventory_maps_only_nonnegative_summary_for_requested_product() -> None:
    seller_id, product_id = uuid4(), uuid4()

    async def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.headers["X-Seller-ID"] == str(seller_id)
        return httpx2.Response(
            200,
            json={
                "seller_id": str(seller_id),
                "product_id": str(product_id),
                "available_units": 1,
                "warehouse_count": 1,
            },
        )

    config = InternalReadClientConfig("https://inventory.internal.test", "marketing-ai", 1, 0)
    async with httpx2.AsyncClient(transport=httpx2.MockTransport(handler)) as http_client:
        summary = await InventoryClient(
            ReadOnlyInternalClient(service="inventory", config=config, http_client=http_client)
        ).get_summary(seller_id=seller_id, product_id=product_id)
    assert summary.available_units == 1


@pytest.mark.anyio
async def test_inventory_rejects_malformed_or_wrong_product_payload() -> None:
    seller_id, product_id = uuid4(), uuid4()
    payload = {
        "seller_id": str(seller_id),
        "product_id": str(uuid4()),
        "available_units": -1,
        "warehouse_count": 1,
    }
    config = InternalReadClientConfig("https://inventory.internal.test", "marketing-ai", 1, 0)
    async with httpx2.AsyncClient(
        transport=httpx2.MockTransport(lambda request: httpx2.Response(200, json=payload))
    ) as http_client:
        with pytest.raises(ApplicationError) as raised:
            await InventoryClient(
                ReadOnlyInternalClient(service="inventory", config=config, http_client=http_client)
            ).get_summary(seller_id=seller_id, product_id=product_id)
    assert raised.value.code == ErrorCode.UPSTREAM_INVALID_RESPONSE
