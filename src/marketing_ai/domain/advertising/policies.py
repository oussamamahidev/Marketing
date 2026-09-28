"""Deterministic seller-scoped advertising policies.

PURPOSE: evaluate eligibility, budget, ownership, publication, CTA, and approval rules.
RESPONSIBILITY: return safe machine-readable decisions; no I/O or configuration loading.
DEPENDENCIES: Python standard library and advertising domain values/entities.
USED BY: application use cases before durable mutations or external dispatch.
TESTED BY: tests/unit/domain/test_budget.py and test_policies.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Mapping
from uuid import UUID

from marketing_ai.domain.advertising.entities import ApprovalRequest
from marketing_ai.domain.advertising.enums import (
    ApprovalStatus,
    CallToAction,
    CampaignObjective,
    DomainError,
    DomainErrorCode,
    PolicyReasonCode,
)
from marketing_ai.domain.advertising.value_objects import DailyBudget, Money, PayloadHash


@dataclass(frozen=True)
class AdvertisingPolicyConfig:
    """Typed values composed from same-named centralized business constants."""

    PLATFORM_CURRENCY: str
    MIN_DAILY_BUDGET_MAD: Money
    MAX_DAILY_BUDGET_MAD: Money
    MAX_DAILY_BUDGET_PER_SELLER_MAD: Money
    MIN_STOCK_UNITS_TO_ADVERTISE: int
    MIN_GROSS_MARGIN_PCT: Decimal
    MAX_ACCEPTABLE_CANCELLATION_RATE_PCT: Decimal
    MAX_ACCEPTABLE_RETURN_RATE_PCT: Decimal
    MIN_ORDERS_FOR_RATE_CONFIDENCE: int
    APPROVAL_PAYLOAD_TTL_MINUTES: int

    def __post_init__(self) -> None:
        monetary_values = (
            self.MIN_DAILY_BUDGET_MAD,
            self.MAX_DAILY_BUDGET_MAD,
            self.MAX_DAILY_BUDGET_PER_SELLER_MAD,
        )
        if not isinstance(self.PLATFORM_CURRENCY, str) or not self.PLATFORM_CURRENCY.strip():
            raise DomainError(
                DomainErrorCode.INVALID_POLICY_CONFIGURATION, "Platform currency is required"
            )
        if any(not isinstance(value, Money) for value in monetary_values):
            raise DomainError(
                DomainErrorCode.INVALID_POLICY_CONFIGURATION, "Budget constants require Money"
            )
        if any(value.currency != self.PLATFORM_CURRENCY for value in monetary_values):
            raise DomainError(
                DomainErrorCode.INVALID_POLICY_CONFIGURATION, "Budget currency must match platform"
            )
        if not (
            self.MIN_DAILY_BUDGET_MAD.centimes
            <= self.MAX_DAILY_BUDGET_MAD.centimes
            <= self.MAX_DAILY_BUDGET_PER_SELLER_MAD.centimes
        ):
            raise DomainError(
                DomainErrorCode.INVALID_POLICY_CONFIGURATION, "Budget constants are inconsistent"
            )
        integer_values = (
            self.MIN_STOCK_UNITS_TO_ADVERTISE,
            self.MIN_ORDERS_FOR_RATE_CONFIDENCE,
            self.APPROVAL_PAYLOAD_TTL_MINUTES,
        )
        if any(
            isinstance(value, bool) or not isinstance(value, int) or value <= 0
            for value in integer_values
        ):
            raise DomainError(
                DomainErrorCode.INVALID_POLICY_CONFIGURATION, "Positive integer constants required"
            )
        percentage_values = (
            self.MIN_GROSS_MARGIN_PCT,
            self.MAX_ACCEPTABLE_CANCELLATION_RATE_PCT,
            self.MAX_ACCEPTABLE_RETURN_RATE_PCT,
        )
        if any(
            not isinstance(value, Decimal) or not value.is_finite() for value in percentage_values
        ):
            raise DomainError(
                DomainErrorCode.INVALID_POLICY_CONFIGURATION, "Percentage constants require Decimal"
            )


@dataclass(frozen=True)
class ProductEligibilityInput:
    stock_units: int
    gross_margin_pct: Decimal
    orders_in_sample: int
    cancellation_rate_pct: Decimal | None
    return_rate_pct: Decimal | None

    def __post_init__(self) -> None:
        if (
            isinstance(self.stock_units, bool)
            or not isinstance(self.stock_units, int)
            or self.stock_units < 0
        ):
            raise DomainError(
                DomainErrorCode.INVALID_VALUE_OBJECT, "Stock must be a non-negative integer"
            )
        if (
            isinstance(self.orders_in_sample, bool)
            or not isinstance(self.orders_in_sample, int)
            or self.orders_in_sample < 0
        ):
            raise DomainError(
                DomainErrorCode.INVALID_VALUE_OBJECT, "Orders must be a non-negative integer"
            )
        decimal_values = (self.gross_margin_pct, self.cancellation_rate_pct, self.return_rate_pct)
        if any(
            value is not None and (not isinstance(value, Decimal) or not value.is_finite())
            for value in decimal_values
        ):
            raise DomainError(
                DomainErrorCode.INVALID_VALUE_OBJECT, "Rates must use finite Decimals"
            )


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    reason_codes: tuple[PolicyReasonCode, ...]

    def __post_init__(self) -> None:
        if not self.reason_codes:
            raise DomainError(
                DomainErrorCode.INVALID_VALUE_OBJECT, "Policy decisions require a reason code"
            )


def _allowed() -> PolicyDecision:
    return PolicyDecision(allowed=True, reason_codes=(PolicyReasonCode.ELIGIBLE,))


def _denied(*reason_codes: PolicyReasonCode) -> PolicyDecision:
    return PolicyDecision(allowed=False, reason_codes=reason_codes)


def _combine(*decisions: PolicyDecision) -> PolicyDecision:
    failures = tuple(
        reason
        for decision in decisions
        if not decision.allowed
        for reason in decision.reason_codes
        if reason != PolicyReasonCode.ELIGIBLE
    )
    return _denied(*dict.fromkeys(failures)) if failures else _allowed()


def stock_eligibility(
    value: ProductEligibilityInput, config: AdvertisingPolicyConfig
) -> PolicyDecision:
    if value.stock_units < config.MIN_STOCK_UNITS_TO_ADVERTISE:
        return _denied(PolicyReasonCode.INSUFFICIENT_STOCK)
    return _allowed()


def gross_margin_eligibility(
    value: ProductEligibilityInput, config: AdvertisingPolicyConfig
) -> PolicyDecision:
    if value.gross_margin_pct < config.MIN_GROSS_MARGIN_PCT:
        return _denied(PolicyReasonCode.GROSS_MARGIN_BELOW_MINIMUM)
    return _allowed()


def cancellation_rate_eligibility(
    value: ProductEligibilityInput, config: AdvertisingPolicyConfig
) -> PolicyDecision:
    if (
        value.orders_in_sample < config.MIN_ORDERS_FOR_RATE_CONFIDENCE
        or value.cancellation_rate_pct is None
    ):
        return _denied(PolicyReasonCode.INSUFFICIENT_DATA)
    if value.cancellation_rate_pct > config.MAX_ACCEPTABLE_CANCELLATION_RATE_PCT:
        return _denied(PolicyReasonCode.CANCELLATION_RATE_EXCEEDS_MAXIMUM)
    return _allowed()


def return_rate_eligibility(
    value: ProductEligibilityInput, config: AdvertisingPolicyConfig
) -> PolicyDecision:
    if (
        value.orders_in_sample < config.MIN_ORDERS_FOR_RATE_CONFIDENCE
        or value.return_rate_pct is None
    ):
        return _denied(PolicyReasonCode.INSUFFICIENT_DATA)
    if value.return_rate_pct > config.MAX_ACCEPTABLE_RETURN_RATE_PCT:
        return _denied(PolicyReasonCode.RETURN_RATE_EXCEEDS_MAXIMUM)
    return _allowed()


def product_eligibility(
    value: ProductEligibilityInput, config: AdvertisingPolicyConfig
) -> PolicyDecision:
    """Compose every required gate; low-confidence rates are failures, never defaults."""
    return _combine(
        stock_eligibility(value, config),
        gross_margin_eligibility(value, config),
        cancellation_rate_eligibility(value, config),
        return_rate_eligibility(value, config),
    )


def validate_daily_budget(
    budget: DailyBudget,
    seller_active_daily_budget: Money,
    config: AdvertisingPolicyConfig,
) -> PolicyDecision:
    if not isinstance(budget, DailyBudget) or not isinstance(seller_active_daily_budget, Money):
        raise DomainError(
            DomainErrorCode.INVALID_VALUE_OBJECT, "Budget validation requires domain money values"
        )
    if seller_active_daily_budget.centimes < 0:
        raise DomainError(
            DomainErrorCode.INVALID_VALUE_OBJECT, "Seller active budget cannot be negative"
        )
    if budget.amount.currency != config.PLATFORM_CURRENCY or (
        seller_active_daily_budget.currency != config.PLATFORM_CURRENCY
    ):
        return _denied(PolicyReasonCode.CURRENCY_MISMATCH)
    if budget.amount.centimes < config.MIN_DAILY_BUDGET_MAD.centimes:
        return _denied(PolicyReasonCode.DAILY_BUDGET_BELOW_MINIMUM)
    if budget.amount.centimes > config.MAX_DAILY_BUDGET_MAD.centimes:
        return _denied(PolicyReasonCode.DAILY_BUDGET_ABOVE_MAXIMUM)
    if (
        seller_active_daily_budget.centimes + budget.amount.centimes
        > config.MAX_DAILY_BUDGET_PER_SELLER_MAD.centimes
    ):
        return _denied(PolicyReasonCode.SELLER_DAILY_BUDGET_CEILING_EXCEEDED)
    return _allowed()


def validate_stock_before_publish(stock_units: int) -> PolicyDecision:
    if isinstance(stock_units, bool) or not isinstance(stock_units, int):
        raise DomainError(DomainErrorCode.INVALID_VALUE_OBJECT, "Stock must be an integer")
    if stock_units <= 0:
        return _denied(PolicyReasonCode.STOCK_EMPTY_FOR_PUBLISH)
    return _allowed()


def require_seller_ownership(expected_seller_id: UUID, resource_seller_id: UUID) -> None:
    if not isinstance(expected_seller_id, UUID) or not isinstance(resource_seller_id, UUID):
        raise DomainError(DomainErrorCode.INVALID_VALUE_OBJECT, "Seller identifiers must be UUIDs")
    if expected_seller_id != resource_seller_id:
        raise DomainError(
            DomainErrorCode.OWNERSHIP_VIOLATION, "Seller scope does not own this resource"
        )


def validate_objective_cta(
    objective: CampaignObjective,
    call_to_action: CallToAction,
    allowed_combinations: Mapping[CampaignObjective, frozenset[CallToAction]],
) -> PolicyDecision:
    if call_to_action not in allowed_combinations.get(objective, frozenset()):
        return _denied(PolicyReasonCode.OBJECTIVE_CTA_NOT_ALLOWED)
    return _allowed()


def validate_exact_payload_approval(
    approval: ApprovalRequest,
    seller_id: UUID,
    campaign_id: UUID,
    payload_hash: PayloadHash,
    now: datetime,
) -> PolicyDecision:
    if approval.seller_id != seller_id or approval.campaign_id != campaign_id:
        return _denied(PolicyReasonCode.APPROVAL_SCOPE_MISMATCH)
    if approval.status != ApprovalStatus.APPROVED:
        return _denied(PolicyReasonCode.APPROVAL_NOT_GRANTED)
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise DomainError(
            DomainErrorCode.INVALID_VALUE_OBJECT, "Approval validation requires an aware time"
        )
    if now >= approval.expires_at:
        return _denied(PolicyReasonCode.APPROVAL_EXPIRED)
    if approval.payload_hash != payload_hash:
        return _denied(PolicyReasonCode.APPROVAL_PAYLOAD_MISMATCH)
    return _allowed()
