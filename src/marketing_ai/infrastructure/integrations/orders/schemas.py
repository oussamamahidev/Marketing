"""Order-outcome response schema for advertising risk inputs.

PURPOSE: normalize historical order outcomes without exposing order-level payloads.
RESPONSIBILITY: validate summary values; no HTTP, customer data, or policy decisions.
DEPENDENCIES: Python standard library and canonical application errors.
USED BY: OrdersClient and ProductAdvertisingContextService.
TESTED BY: tests/contract/internal/test_orders_contract.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Mapping
from uuid import UUID

from marketing_ai.core.errors import ApplicationError, ErrorCode


def _invalid() -> ApplicationError:
    return ApplicationError(ErrorCode.UPSTREAM_INVALID_RESPONSE)


def _rate(payload: Mapping[str, object], key: str) -> Decimal:
    raw = payload.get(key)
    if isinstance(raw, float):
        raise _invalid()
    try:
        value = Decimal(str(raw))
    except InvalidOperation, ValueError:
        raise _invalid() from None
    if not value.is_finite() or value < Decimal("0") or value > Decimal("100"):
        raise _invalid()
    return value


@dataclass(frozen=True)
class OrderOutcomeSummary:
    product_id: UUID
    seller_id: UUID
    orders_in_sample: int
    cancellation_rate_pct: Decimal
    return_rate_pct: Decimal

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> "OrderOutcomeSummary":
        product_id = payload.get("product_id")
        seller_id = payload.get("seller_id")
        orders = payload.get("orders_in_sample")
        if (
            not isinstance(product_id, str)
            or not isinstance(seller_id, str)
            or isinstance(orders, bool)
            or not isinstance(orders, int)
            or orders < 0
        ):
            raise _invalid()
        try:
            return cls(
                product_id=UUID(product_id),
                seller_id=UUID(seller_id),
                orders_in_sample=orders,
                cancellation_rate_pct=_rate(payload, "cancellation_rate_pct"),
                return_rate_pct=_rate(payload, "return_rate_pct"),
            )
        except ValueError:
            raise _invalid() from None
