"""Immutable decimal-safe advertising value objects.

PURPOSE: protect money, daily-budget, and canonical-payload invariants.
RESPONSIBILITY: represent values only; no policy, repository, or external operation.
DEPENDENCIES: Python standard library and advertising error vocabulary.
USED BY: advertising entities and deterministic policies.
TESTED BY: tests/unit/domain/test_budget.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from hashlib import sha256

from marketing_ai.domain.advertising.enums import DomainError, DomainErrorCode

CENTIMES_PER_MAJOR_UNIT = 100


@dataclass(frozen=True, order=True)
class Money:
    """Currency amount stored as integer centimes, never a binary float."""

    centimes: int
    currency: str

    def __post_init__(self) -> None:
        if isinstance(self.centimes, bool) or not isinstance(self.centimes, int):
            raise DomainError(
                DomainErrorCode.INVALID_VALUE_OBJECT, "Money requires integer centimes"
            )
        if not isinstance(self.currency, str) or not self.currency.strip():
            raise DomainError(DomainErrorCode.INVALID_VALUE_OBJECT, "Money requires a currency")

    @classmethod
    def from_decimal(cls, amount: Decimal, currency: str) -> "Money":
        if not isinstance(amount, Decimal) or not amount.is_finite():
            raise DomainError(
                DomainErrorCode.INVALID_VALUE_OBJECT, "Money requires a finite Decimal"
            )
        numerator, denominator = amount.as_integer_ratio()
        centimes, remainder = divmod(numerator * CENTIMES_PER_MAJOR_UNIT, denominator)
        if remainder:
            raise DomainError(
                DomainErrorCode.INVALID_VALUE_OBJECT,
                "Money amount cannot contain fractions of a centime",
            )
        return cls(centimes=centimes, currency=currency)

    def as_decimal(self) -> Decimal:
        return Decimal(self.centimes) / Decimal(CENTIMES_PER_MAJOR_UNIT)


@dataclass(frozen=True)
class DailyBudget:
    """A positive, immutable amount intended for one calendar day."""

    amount: Money

    def __post_init__(self) -> None:
        if not isinstance(self.amount, Money) or self.amount.centimes <= 0:
            raise DomainError(
                DomainErrorCode.INVALID_VALUE_OBJECT, "Daily budget must be positive money"
            )


@dataclass(frozen=True)
class PayloadHash:
    """SHA-256 digest of a caller-supplied canonical external-action payload."""

    digest: str

    def __post_init__(self) -> None:
        expected_length = sha256().digest_size * 2
        if (
            not isinstance(self.digest, str)
            or len(self.digest) != expected_length
            or self.digest.lower() != self.digest
            or any(character not in "0123456789abcdef" for character in self.digest)
        ):
            raise DomainError(
                DomainErrorCode.INVALID_VALUE_OBJECT, "Payload hash must be a SHA-256 hex digest"
            )

    @classmethod
    def from_canonical_bytes(cls, payload: bytes) -> "PayloadHash":
        if not isinstance(payload, bytes):
            raise DomainError(
                DomainErrorCode.INVALID_VALUE_OBJECT, "Canonical payload must be bytes"
            )
        return cls(digest=sha256(payload).hexdigest())
