"""Catalog response schema isolated from raw internal API payloads.

PURPOSE: validate only product advertising facts consumed by the application.
RESPONSIBILITY: map raw mappings to immutable values; no HTTP or policy decisions.
DEPENDENCIES: Python standard library and canonical application errors.
USED BY: CatalogClient and ProductAdvertisingContextService.
TESTED BY: tests/contract/internal/test_catalog_contract.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Mapping
from uuid import UUID

from marketing_ai.core.errors import ApplicationError, ErrorCode


def _invalid() -> ApplicationError:
    return ApplicationError(ErrorCode.UPSTREAM_INVALID_RESPONSE)


def _uuid(payload: Mapping[str, object], key: str) -> UUID:
    value = payload.get(key)
    if not isinstance(value, str):
        raise _invalid()
    try:
        return UUID(value)
    except ValueError:
        raise _invalid() from None


def _text(payload: Mapping[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise _invalid()
    return value


@dataclass(frozen=True)
class CatalogProduct:
    product_id: UUID
    seller_id: UUID
    name: str
    price_centimes: int
    gross_margin_pct: Decimal | None

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> "CatalogProduct":
        price_centimes = payload.get("price_centimes")
        if (
            isinstance(price_centimes, bool)
            or not isinstance(price_centimes, int)
            or price_centimes < 0
        ):
            raise _invalid()
        raw_margin = payload.get("gross_margin_pct")
        if raw_margin is None:
            margin = None
        elif isinstance(raw_margin, float):
            raise _invalid()
        else:
            try:
                margin = Decimal(str(raw_margin))
            except InvalidOperation, ValueError:
                raise _invalid() from None
            if not margin.is_finite() or margin < Decimal("0") or margin > Decimal("100"):
                raise _invalid()
        return cls(
            product_id=_uuid(payload, "product_id"),
            seller_id=_uuid(payload, "seller_id"),
            name=_text(payload, "name"),
            price_centimes=price_centimes,
            gross_margin_pct=margin,
        )
