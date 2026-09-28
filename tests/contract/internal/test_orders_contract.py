"""P06 Orders read-adapter contract tests.

PURPOSE: prove aggregate-order mapping preserves Decimal-safe risk inputs.
RESPONSIBILITY: exercise read-only outcome contracts without customer records or writes.
DEPENDENCIES: httpx2 mock transport and P06 adapter interfaces.
USED BY: P06 regression suite.
TESTED BY: this module.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import httpx2
import pytest

from marketing_ai.core.errors import ApplicationError, ErrorCode
from marketing_ai.infrastructure.integrations.common import (
    InternalReadClientConfig,
    ReadOnlyInternalClient,
)
from marketing_ai.infrastructure.integrations.orders.client import OrdersClient


@pytest.mark.anyio
async def test_orders_maps_aggregate_outcomes_without_binary_float_rates() -> None:
    seller_id, product_id = uuid4(), uuid4()
    payload = {
        "seller_id": str(seller_id),
        "product_id": str(product_id),
        "orders_in_sample": 1,
        "cancellation_rate_pct": "35",
        "return_rate_pct": "15",
    }
    config = InternalReadClientConfig("https://orders.internal.test", "marketing-ai", 1, 0)
    async with httpx2.AsyncClient(
        transport=httpx2.MockTransport(lambda request: httpx2.Response(200, json=payload))
    ) as http_client:
        summary = await OrdersClient(
            ReadOnlyInternalClient(service="orders", config=config, http_client=http_client)
        ).get_outcome_summary(seller_id=seller_id, product_id=product_id)
    assert summary.cancellation_rate_pct == Decimal("35")


@pytest.mark.anyio
async def test_orders_rejects_float_rate_and_maps_dependency_unavailable_after_bounded_retries() -> (
    None
):
    seller_id, product_id = uuid4(), uuid4()
    malformed = {
        "seller_id": str(seller_id),
        "product_id": str(product_id),
        "orders_in_sample": 1,
        "cancellation_rate_pct": 35.0,
        "return_rate_pct": "15",
    }
    config = InternalReadClientConfig("https://orders.internal.test", "marketing-ai", 1, 1)
    async with httpx2.AsyncClient(
        transport=httpx2.MockTransport(lambda request: httpx2.Response(200, json=malformed))
    ) as http_client:
        with pytest.raises(ApplicationError) as malformed_error:
            await OrdersClient(
                ReadOnlyInternalClient(service="orders", config=config, http_client=http_client)
            ).get_outcome_summary(seller_id=seller_id, product_id=product_id)
    assert malformed_error.value.code == ErrorCode.UPSTREAM_INVALID_RESPONSE

    calls = 0

    async def unavailable(request: httpx2.Request) -> httpx2.Response:
        nonlocal calls
        calls += 1
        return httpx2.Response(503)

    async with httpx2.AsyncClient(transport=httpx2.MockTransport(unavailable)) as http_client:
        with pytest.raises(ApplicationError) as unavailable_error:
            await OrdersClient(
                ReadOnlyInternalClient(service="orders", config=config, http_client=http_client)
            ).get_outcome_summary(seller_id=seller_id, product_id=product_id)
    assert unavailable_error.value.code == ErrorCode.DEPENDENCY_UNAVAILABLE
    assert calls == config.max_retries + 1
