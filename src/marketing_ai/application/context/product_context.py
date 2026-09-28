"""Application service that aggregates read-only product advertising context.

PURPOSE: coordinate narrow seller-scoped reads into one typed product context.
RESPONSIBILITY: aggregate validated summaries; no HTTP, policy decision, or persistence.
DEPENDENCIES: Python standard library and application-owned structural interfaces.
USED BY: future proposal-generation and deterministic validation use cases.
TESTED BY: tests/contract/internal/test_catalog_contract.py.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol
from uuid import UUID


class ProductMetadata(Protocol):
    @property
    def product_id(self) -> UUID: ...

    @property
    def seller_id(self) -> UUID: ...

    @property
    def name(self) -> str: ...

    @property
    def price_centimes(self) -> int: ...

    @property
    def gross_margin_pct(self) -> Decimal | None: ...


class InventoryMetadata(Protocol):
    @property
    def product_id(self) -> UUID: ...

    @property
    def seller_id(self) -> UUID: ...

    @property
    def available_units(self) -> int: ...

    @property
    def warehouse_count(self) -> int: ...


class OrderOutcomeMetadata(Protocol):
    @property
    def product_id(self) -> UUID: ...

    @property
    def seller_id(self) -> UUID: ...

    @property
    def orders_in_sample(self) -> int: ...

    @property
    def cancellation_rate_pct(self) -> Decimal: ...

    @property
    def return_rate_pct(self) -> Decimal: ...


class CreativeMetadata(Protocol):
    @property
    def creative_id(self) -> UUID: ...

    @property
    def seller_id(self) -> UUID: ...

    @property
    def name(self) -> str: ...

    @property
    def media_url(self) -> str: ...

    @property
    def media_type(self) -> str: ...


class CatalogProductReader(Protocol):
    async def get_product(self, *, seller_id: UUID, product_id: UUID) -> ProductMetadata: ...


class InventorySummaryReader(Protocol):
    async def get_summary(self, *, seller_id: UUID, product_id: UUID) -> InventoryMetadata: ...


class OrderOutcomeReader(Protocol):
    async def get_outcome_summary(
        self, *, seller_id: UUID, product_id: UUID
    ) -> OrderOutcomeMetadata: ...


class CreativeReader(Protocol):
    async def get_creative(self, *, seller_id: UUID, creative_id: UUID) -> CreativeMetadata: ...


@dataclass(frozen=True)
class ProductAdvertisingContext:
    seller_id: UUID
    product: ProductMetadata
    inventory: InventoryMetadata
    order_outcomes: OrderOutcomeMetadata
    creative: CreativeMetadata


class ProductAdvertisingContextService:
    """All facts are required; missing dependency data fails closed for later policy evaluation."""

    def __init__(
        self,
        *,
        catalog: CatalogProductReader,
        inventory: InventorySummaryReader,
        orders: OrderOutcomeReader,
        content_hub: CreativeReader,
    ) -> None:
        self._catalog = catalog
        self._inventory = inventory
        self._orders = orders
        self._content_hub = content_hub

    async def get_context(
        self, *, seller_id: UUID, product_id: UUID, creative_id: UUID
    ) -> ProductAdvertisingContext:
        product, inventory, order_outcomes, creative = await asyncio.gather(
            self._catalog.get_product(seller_id=seller_id, product_id=product_id),
            self._inventory.get_summary(seller_id=seller_id, product_id=product_id),
            self._orders.get_outcome_summary(seller_id=seller_id, product_id=product_id),
            self._content_hub.get_creative(seller_id=seller_id, creative_id=creative_id),
        )
        return ProductAdvertisingContext(
            seller_id=seller_id,
            product=product,
            inventory=inventory,
            order_outcomes=order_outcomes,
            creative=creative,
        )
