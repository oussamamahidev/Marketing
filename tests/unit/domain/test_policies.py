"""P05 deterministic advertising policy tests; no external dependency."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from marketing_ai.core.config import Settings
from marketing_ai.domain.advertising.entities import CampaignDraft
from marketing_ai.domain.advertising.enums import (
    CallToAction,
    CampaignObjective,
    CampaignTrigger,
    PolicyReasonCode,
)
from marketing_ai.domain.advertising.policies import (
    AdvertisingPolicyConfig,
    ProductEligibilityInput,
    product_eligibility,
    require_seller_ownership,
    validate_exact_payload_approval,
    validate_objective_cta,
    validate_stock_before_publish,
)
from marketing_ai.domain.advertising.services import (
    approve_approval_request,
    create_approval_request,
    transition_campaign,
)
from marketing_ai.domain.advertising.value_objects import DailyBudget, Money, PayloadHash


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


def validated_campaign(settings: Settings) -> CampaignDraft:
    config = policy_config(settings)
    draft = CampaignDraft(
        campaign_id=uuid4(),
        seller_id=uuid4(),
        ad_account_link_id=uuid4(),
        product_reference="catalog-product-1",
        objective=CampaignObjective.SALES,
        call_to_action=CallToAction.SHOP_NOW,
        daily_budget=DailyBudget(config.MIN_DAILY_BUDGET_MAD),
        payload_hash=PayloadHash.from_canonical_bytes(b'{"version":1}'),
    )
    return transition_campaign(draft, CampaignTrigger.VALIDATE)


def test_product_eligibility_returns_each_failing_machine_code(settings: Settings) -> None:
    config = policy_config(settings)
    decision = product_eligibility(
        ProductEligibilityInput(
            stock_units=config.MIN_STOCK_UNITS_TO_ADVERTISE - 1,
            gross_margin_pct=config.MIN_GROSS_MARGIN_PCT - Decimal("0.01"),
            orders_in_sample=config.MIN_ORDERS_FOR_RATE_CONFIDENCE,
            cancellation_rate_pct=config.MAX_ACCEPTABLE_CANCELLATION_RATE_PCT + Decimal("0.01"),
            return_rate_pct=config.MAX_ACCEPTABLE_RETURN_RATE_PCT + Decimal("0.01"),
        ),
        config,
    )

    assert not decision.allowed
    assert set(decision.reason_codes) == {
        PolicyReasonCode.INSUFFICIENT_STOCK,
        PolicyReasonCode.GROSS_MARGIN_BELOW_MINIMUM,
        PolicyReasonCode.CANCELLATION_RATE_EXCEEDS_MAXIMUM,
        PolicyReasonCode.RETURN_RATE_EXCEEDS_MAXIMUM,
    }


def test_low_order_sample_is_insufficient_data_not_a_default_pass(settings: Settings) -> None:
    config = policy_config(settings)
    decision = product_eligibility(
        ProductEligibilityInput(
            stock_units=config.MIN_STOCK_UNITS_TO_ADVERTISE,
            gross_margin_pct=config.MIN_GROSS_MARGIN_PCT,
            orders_in_sample=config.MIN_ORDERS_FOR_RATE_CONFIDENCE - 1,
            cancellation_rate_pct=Decimal("0"),
            return_rate_pct=Decimal("0"),
        ),
        config,
    )

    assert not decision.allowed
    assert decision.reason_codes == (PolicyReasonCode.INSUFFICIENT_DATA,)


def test_publish_stock_cta_and_tenant_ownership_policies() -> None:
    seller_id = uuid4()
    assert not validate_stock_before_publish(0).allowed
    assert validate_stock_before_publish(1).allowed
    assert validate_objective_cta(
        CampaignObjective.SALES,
        CallToAction.SHOP_NOW,
        {CampaignObjective.SALES: frozenset({CallToAction.SHOP_NOW})},
    ).allowed
    require_seller_ownership(seller_id, seller_id)


def test_approval_is_invalid_when_any_payload_byte_changes(settings: Settings) -> None:
    config = policy_config(settings)
    campaign = validated_campaign(settings)
    now = datetime.now(UTC)
    approval = approve_approval_request(
        create_approval_request(uuid4(), campaign, now, config), uuid4()
    )

    assert validate_exact_payload_approval(
        approval, campaign.seller_id, campaign.campaign_id, campaign.payload_hash, now
    ).allowed
    changed_payload = PayloadHash.from_canonical_bytes(b'{"version":2}')
    decision = validate_exact_payload_approval(
        approval, campaign.seller_id, campaign.campaign_id, changed_payload, now
    )
    assert decision.reason_codes == (PolicyReasonCode.APPROVAL_PAYLOAD_MISMATCH,)


def test_tenant_mismatch_expired_approval_and_disallowed_cta_fail_closed(
    settings: Settings,
) -> None:
    import pytest

    from marketing_ai.domain.advertising.enums import DomainError, DomainErrorCode

    config = policy_config(settings)
    campaign = validated_campaign(settings)
    now = datetime.now(UTC)
    approval = approve_approval_request(
        create_approval_request(uuid4(), campaign, now, config), uuid4()
    )

    with pytest.raises(DomainError) as ownership_error:
        require_seller_ownership(campaign.seller_id, uuid4())
    assert ownership_error.value.code == DomainErrorCode.OWNERSHIP_VIOLATION
    assert validate_objective_cta(
        CampaignObjective.SALES,
        CallToAction.CONTACT_US,
        {CampaignObjective.SALES: frozenset({CallToAction.SHOP_NOW})},
    ).reason_codes == (PolicyReasonCode.OBJECTIVE_CTA_NOT_ALLOWED,)
    assert validate_exact_payload_approval(
        approval,
        campaign.seller_id,
        campaign.campaign_id,
        campaign.payload_hash,
        approval.expires_at,
    ).reason_codes == (PolicyReasonCode.APPROVAL_EXPIRED,)


def test_malformed_snapshot_order_count_raises_a_typed_domain_error() -> None:
    import pytest

    from marketing_ai.domain.advertising.entities import PerformanceSnapshot
    from marketing_ai.domain.advertising.enums import DomainError, DomainErrorCode

    with pytest.raises(DomainError) as malformed_snapshot:
        PerformanceSnapshot(
            snapshot_id=uuid4(),
            seller_id=uuid4(),
            campaign_id=uuid4(),
            observed_at=datetime.now(UTC),
            spend=Money(centimes=0, currency="MAD"),
            orders="not-an-integer",  # type: ignore[arg-type]
        )
    assert malformed_snapshot.value.code == DomainErrorCode.INVALID_VALUE_OBJECT
