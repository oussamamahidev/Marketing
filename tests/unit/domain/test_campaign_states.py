"""P05 campaign lifecycle tests; no database, HTTP, provider, or LLM dependency."""

from __future__ import annotations

from uuid import uuid4

import pytest

from marketing_ai.domain.advertising.entities import CampaignDraft
from marketing_ai.domain.advertising.enums import (
    CallToAction,
    CampaignObjective,
    CampaignState,
    CampaignTrigger,
    DomainError,
    DomainErrorCode,
)
from marketing_ai.domain.advertising.services import CAMPAIGN_TRANSITIONS, transition_campaign
from marketing_ai.domain.advertising.value_objects import DailyBudget, Money, PayloadHash


def campaign() -> CampaignDraft:
    return CampaignDraft(
        campaign_id=uuid4(),
        seller_id=uuid4(),
        ad_account_link_id=uuid4(),
        product_reference="catalog-product-1",
        objective=CampaignObjective.SALES,
        call_to_action=CallToAction.SHOP_NOW,
        daily_budget=DailyBudget(Money(centimes=1, currency="MAD")),
        payload_hash=PayloadHash.from_canonical_bytes(b'{"campaign":"one"}'),
    )


def test_campaign_can_only_follow_the_explicit_transition_table() -> None:
    draft = campaign()
    triggers = (
        CampaignTrigger.VALIDATE,
        CampaignTrigger.REQUEST_APPROVAL,
        CampaignTrigger.APPROVE,
        CampaignTrigger.START_EXECUTION,
        CampaignTrigger.REQUIRE_RECONCILIATION,
        CampaignTrigger.RECONCILE_PUBLISHED,
    )

    for trigger in triggers:
        draft = transition_campaign(draft, trigger)

    assert draft.state == CampaignState.PUBLISHED
    assert draft.version == len(triggers) + 1
    assert (
        CAMPAIGN_TRANSITIONS[(CampaignState.EXECUTING, CampaignTrigger.MARK_FAILED)]
        == CampaignState.FAILED
    )


def test_absent_transition_raises_a_typed_domain_error() -> None:
    with pytest.raises(DomainError) as raised:
        transition_campaign(campaign(), CampaignTrigger.START_EXECUTION)

    assert raised.value.code == DomainErrorCode.INVALID_STATE_TRANSITION


def test_state_cannot_be_selected_or_mutated_by_campaign_constructor() -> None:
    draft = campaign()
    with pytest.raises(AttributeError):
        draft.state = CampaignState.PUBLISHED  # type: ignore[misc]
    with pytest.raises(TypeError):
        CampaignDraft(  # type: ignore[call-arg]
            campaign_id=uuid4(),
            seller_id=uuid4(),
            ad_account_link_id=uuid4(),
            product_reference="catalog-product-1",
            objective=CampaignObjective.SALES,
            call_to_action=CallToAction.SHOP_NOW,
            daily_budget=DailyBudget(Money(centimes=1, currency="MAD")),
            payload_hash=PayloadHash.from_canonical_bytes(b"payload"),
            state=CampaignState.PUBLISHED,
        )


def test_terminal_states_and_malformed_identifiers_fail_closed() -> None:
    terminal = campaign()
    for trigger in (CampaignTrigger.VALIDATE, CampaignTrigger.REQUEST_APPROVAL):
        terminal = transition_campaign(terminal, trigger)
    terminal = transition_campaign(terminal, CampaignTrigger.REJECT)

    with pytest.raises(DomainError) as raised:
        transition_campaign(terminal, CampaignTrigger.VALIDATE)
    assert raised.value.code == DomainErrorCode.INVALID_STATE_TRANSITION

    with pytest.raises(DomainError) as invalid_identifier:
        CampaignDraft(
            campaign_id="not-a-uuid",  # type: ignore[arg-type]
            seller_id=uuid4(),
            ad_account_link_id=uuid4(),
            product_reference="catalog-product-1",
            objective=CampaignObjective.SALES,
            call_to_action=CallToAction.SHOP_NOW,
            daily_budget=DailyBudget(Money(centimes=1, currency="MAD")),
            payload_hash=PayloadHash.from_canonical_bytes(b"payload"),
        )
    assert invalid_identifier.value.code == DomainErrorCode.INVALID_VALUE_OBJECT
