"""Campaign lifecycle transition and approval-construction services.

PURPOSE: apply the explicit lifecycle table without I/O.
RESPONSIBILITY: enforce transitions and approval expiry; no provider dispatch or persistence.
DEPENDENCIES: Python standard library and advertising entities, policies, and enums.
USED BY: application use cases coordinating repositories and gateways.
TESTED BY: tests/unit/domain/test_campaign_states.py and test_policies.py.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from types import MappingProxyType
from typing import Mapping
from uuid import UUID

from marketing_ai.domain.advertising.entities import ApprovalRequest, CampaignDraft
from marketing_ai.domain.advertising.enums import (
    ApprovalStatus,
    CampaignState,
    CampaignTrigger,
    DomainError,
    DomainErrorCode,
)
from marketing_ai.domain.advertising.policies import AdvertisingPolicyConfig

CAMPAIGN_TRANSITIONS: Mapping[tuple[CampaignState, CampaignTrigger], CampaignState] = (
    MappingProxyType(
        {
            (CampaignState.DRAFT, CampaignTrigger.VALIDATE): CampaignState.VALIDATED,
            (
                CampaignState.VALIDATED,
                CampaignTrigger.REQUEST_APPROVAL,
            ): CampaignState.PENDING_APPROVAL,
            (CampaignState.PENDING_APPROVAL, CampaignTrigger.APPROVE): CampaignState.APPROVED,
            (CampaignState.PENDING_APPROVAL, CampaignTrigger.REJECT): CampaignState.REJECTED,
            (CampaignState.APPROVED, CampaignTrigger.START_EXECUTION): CampaignState.EXECUTING,
            (CampaignState.EXECUTING, CampaignTrigger.CONFIRM_PUBLISHED): CampaignState.PUBLISHED,
            (CampaignState.EXECUTING, CampaignTrigger.MARK_FAILED): CampaignState.FAILED,
            (CampaignState.EXECUTING, CampaignTrigger.REQUIRE_RECONCILIATION): (
                CampaignState.RECONCILIATION_REQUIRED
            ),
            (CampaignState.RECONCILIATION_REQUIRED, CampaignTrigger.RECONCILE_PUBLISHED): (
                CampaignState.PUBLISHED
            ),
            (
                CampaignState.RECONCILIATION_REQUIRED,
                CampaignTrigger.RECONCILE_FAILED,
            ): CampaignState.FAILED,
        }
    )
)


def transition_campaign(campaign: CampaignDraft, trigger: CampaignTrigger) -> CampaignDraft:
    """Return a new campaign only when the documented transition exists."""
    if not isinstance(campaign, CampaignDraft) or not isinstance(trigger, CampaignTrigger):
        raise DomainError(
            DomainErrorCode.INVALID_VALUE_OBJECT, "Campaign and trigger must use domain types"
        )
    state = CAMPAIGN_TRANSITIONS.get((campaign.state, trigger))
    if state is None:
        raise DomainError(
            DomainErrorCode.INVALID_STATE_TRANSITION, "Campaign transition is not allowed"
        )
    return campaign._with_transition(state)


def create_approval_request(
    approval_id: UUID,
    campaign: CampaignDraft,
    requested_at: datetime,
    config: AdvertisingPolicyConfig,
) -> ApprovalRequest:
    if campaign.state != CampaignState.VALIDATED:
        raise DomainError(
            DomainErrorCode.INVALID_APPROVAL, "Only validated campaigns may request approval"
        )
    if (
        not isinstance(requested_at, datetime)
        or requested_at.tzinfo is None
        or requested_at.utcoffset() is None
    ):
        raise DomainError(
            DomainErrorCode.INVALID_VALUE_OBJECT, "Approval request time must be timezone-aware"
        )
    return ApprovalRequest(
        approval_id=approval_id,
        seller_id=campaign.seller_id,
        campaign_id=campaign.campaign_id,
        payload_hash=campaign.payload_hash,
        requested_at=requested_at,
        expires_at=requested_at + timedelta(minutes=config.APPROVAL_PAYLOAD_TTL_MINUTES),
    )


def approve_approval_request(request: ApprovalRequest, approver_id: UUID) -> ApprovalRequest:
    if request.status != ApprovalStatus.PENDING:
        raise DomainError(DomainErrorCode.INVALID_APPROVAL, "Only pending approvals may be granted")
    return request._approved_by(approver_id)
