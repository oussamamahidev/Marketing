"""P05 decimal-safe daily budget tests; no external dependency."""

from __future__ import annotations

from decimal import Decimal

import pytest

from marketing_ai.core.config import Settings
from marketing_ai.domain.advertising.enums import DomainError, PolicyReasonCode
from marketing_ai.domain.advertising.policies import AdvertisingPolicyConfig, validate_daily_budget
from marketing_ai.domain.advertising.value_objects import DailyBudget, Money


def policy_config(settings: Settings) -> AdvertisingPolicyConfig:
    currency = settings.PLATFORM_CURRENCY
    return AdvertisingPolicyConfig(
        PLATFORM_CURRENCY=currency,
        MIN_DAILY_BUDGET_MAD=Money.from_decimal(settings.MIN_DAILY_BUDGET_MAD, currency),
        MAX_DAILY_BUDGET_MAD=Money.from_decimal(settings.MAX_DAILY_BUDGET_MAD, currency),
        MAX_DAILY_BUDGET_PER_SELLER_MAD=Money.from_decimal(
            settings.MAX_DAILY_BUDGET_PER_SELLER_MAD, currency
        ),
        MIN_STOCK_UNITS_TO_ADVERTISE=settings.MIN_STOCK_UNITS_TO_ADVERTISE,
        MIN_GROSS_MARGIN_PCT=settings.MIN_GROSS_MARGIN_PCT,
        MAX_ACCEPTABLE_CANCELLATION_RATE_PCT=settings.MAX_ACCEPTABLE_CANCELLATION_RATE_PCT,
        MAX_ACCEPTABLE_RETURN_RATE_PCT=settings.MAX_ACCEPTABLE_RETURN_RATE_PCT,
        MIN_ORDERS_FOR_RATE_CONFIDENCE=settings.MIN_ORDERS_FOR_RATE_CONFIDENCE,
        APPROVAL_PAYLOAD_TTL_MINUTES=settings.APPROVAL_PAYLOAD_TTL_MINUTES,
    )


def test_money_is_exact_and_rejects_binary_float() -> None:
    money = Money.from_decimal(Decimal("50.00"), "MAD")

    assert money.centimes == 5_000
    assert money.as_decimal() == Decimal("50")
    with pytest.raises(DomainError):
        Money.from_decimal(50.0, "MAD")  # type: ignore[arg-type]
    with pytest.raises(DomainError):
        Money.from_decimal(Decimal("1.001"), "MAD")


def test_daily_budget_uses_named_maximum_and_seller_ceiling(settings: Settings) -> None:
    config = policy_config(settings)
    maximum = DailyBudget(config.MAX_DAILY_BUDGET_MAD)
    below_minimum = DailyBudget(Money(config.MIN_DAILY_BUDGET_MAD.centimes - 1, "MAD"))
    seller_ceiling = Money(
        config.MAX_DAILY_BUDGET_PER_SELLER_MAD.centimes - maximum.amount.centimes + 1,
        "MAD",
    )

    assert validate_daily_budget(maximum, Money(0, "MAD"), config).allowed
    assert validate_daily_budget(below_minimum, Money(0, "MAD"), config).reason_codes == (
        PolicyReasonCode.DAILY_BUDGET_BELOW_MINIMUM,
    )
    assert validate_daily_budget(maximum, seller_ceiling, config).reason_codes == (
        PolicyReasonCode.SELLER_DAILY_BUDGET_CEILING_EXCEEDED,
    )


def test_daily_budget_rejects_above_maximum_and_negative_active_total(settings: Settings) -> None:
    config = policy_config(settings)
    above_maximum = DailyBudget(Money(config.MAX_DAILY_BUDGET_MAD.centimes + 1, "MAD"))

    assert validate_daily_budget(above_maximum, Money(0, "MAD"), config).reason_codes == (
        PolicyReasonCode.DAILY_BUDGET_ABOVE_MAXIMUM,
    )
    with pytest.raises(DomainError):
        validate_daily_budget(
            DailyBudget(config.MIN_DAILY_BUDGET_MAD),
            Money(-1, config.PLATFORM_CURRENCY),
            config,
        )
