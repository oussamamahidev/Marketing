"""Inventory response schema for advertising eligibility inputs.

PURPOSE: normalize the warehouse summary needed by product-context aggregation.
RESPONSIBILITY: validate immutable inventory facts; no HTTP, stock policy, or writes.
DEPENDENCIES: Python standard library and canonical application errors.
USED BY: InventoryClient and ProductAdvertisingContextService.
TESTED BY: tests/contract/internal/test_inventory_contract.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping
from uuid import UUID

from marketing_ai.core.errors import ApplicationError, ErrorCode


def _invalid() -> ApplicationError:
    return ApplicationError(ErrorCode.UPSTREAM_INVALID_RESPONSE)


@dataclass(frozen=True)
class InventorySummary:
    product_id: UUID
    seller_id: UUID
    available_units: int
    warehouse_count: int

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> "InventorySummary":
        raw_product_id = payload.get("product_id")
        raw_seller_id = payload.get("seller_id")
        available_units = payload.get("available_units")
        warehouse_count = payload.get("warehouse_count")
        if (
            not isinstance(raw_product_id, str)
            or not isinstance(raw_seller_id, str)
            or isinstance(available_units, bool)
            or not isinstance(available_units, int)
            or available_units < 0
            or isinstance(warehouse_count, bool)
            or not isinstance(warehouse_count, int)
            or warehouse_count < 0
        ):
            raise _invalid()
        try:
            return cls(
                product_id=UUID(raw_product_id),
                seller_id=UUID(raw_seller_id),
                available_units=available_units,
                warehouse_count=warehouse_count,
            )
        except ValueError:
            raise _invalid() from None
