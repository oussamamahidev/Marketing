"""Immutable seller-scoped advertising entities.

PURPOSE: model advertising facts without persistence or provider dependencies.
RESPONSIBILITY: protect local identity and value invariants; no state transition policy.
DEPENDENCIES: Python standard library and advertising value/enumeration types.
USED BY: application use cases, policies, services, and repository adapters.
TESTED BY: tests/unit/domain/test_campaign_states.py and test_policies.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
from uuid import UUID

from marketing_ai.domain.advertising.enums import (
    ApprovalStatus,
    CallToAction,
    CampaignObjective,
    CampaignState,
    DomainError,
    DomainErrorCode,
)
from marketing_ai.domain.advertising.value_objects import DailyBudget, Money, PayloadHash

INITIAL_CAMPAIGN_VERSION = 1


def _require_uuid(value: UUID, field_name: str) -> None:
    if not isinstance(value, UUID):
        raise DomainError(DomainErrorCode.INVALID_VALUE_OBJECT, f"{field_name} must be a UUID")


def _require_aware_datetime(value: datetime, field_name: str) -> None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise DomainError(
            DomainErrorCode.INVALID_VALUE_OBJECT, f"{field_name} must be timezone-aware"
        )


def _require_text(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise DomainError(DomainErrorCode.INVALID_VALUE_OBJECT, f"{field_name} must be non-empty")


@dataclass(frozen=True)
class MetaConnection:
    connection_id: UUID
    seller_id: UUID
    identity_reference: str
    expires_at: datetime

    def __post_init__(self) -> None:
        _require_uuid(self.connection_id, "connection_id")
        _require_uuid(self.seller_id, "seller_id")
        _require_text(self.identity_reference, "identity_reference")
        _require_aware_datetime(self.expires_at, "expires_at")


@dataclass(frozen=True)
class AdAccountLink:
    link_id: UUID
    seller_id: UUID
    connection_id: UUID
    external_account_reference: str
    currency: str

    def __post_init__(self) -> None:
        _require_uuid(self.link_id, "link_id")
        _require_uuid(self.seller_id, "seller_id")
        _require_uuid(self.connection_id, "connection_id")
        _require_text(self.external_account_reference, "external_account_reference")
        _require_text(self.currency, "currency")


@dataclass(frozen=True)
class SellerMarketingProfile:
    seller_id: UUID
    meta_connection: MetaConnection | None
    ad_account_links: tuple[AdAccountLink, ...]

    def __post_init__(self) -> None:
        _require_uuid(self.seller_id, "seller_id")
        if self.meta_connection is not None and self.meta_connection.seller_id != self.seller_id:
            raise DomainError(
                DomainErrorCode.OWNERSHIP_VIOLATION, "Meta connection belongs to another seller"
            )
        if any(link.seller_id != self.seller_id for link in self.ad_account_links):
            raise DomainError(
                DomainErrorCode.OWNERSHIP_VIOLATION, "Ad account link belongs to another seller"
            )


@dataclass(frozen=True)
class CampaignDraft:
    campaign_id: UUID
    seller_id: UUID
    ad_account_link_id: UUID
    product_reference: str
    objective: CampaignObjective
    call_to_action: CallToAction
    daily_budget: DailyBudget
    payload_hash: PayloadHash
    state: CampaignState = field(default=CampaignState.DRAFT, init=False)
    version: int = field(default=INITIAL_CAMPAIGN_VERSION, init=False)

    def __post_init__(self) -> None:
        _require_uuid(self.campaign_id, "campaign_id")
        _require_uuid(self.seller_id, "seller_id")
        _require_uuid(self.ad_account_link_id, "ad_account_link_id")
        _require_text(self.product_reference, "product_reference")
        if not isinstance(self.objective, CampaignObjective) or not isinstance(
            self.call_to_action, CallToAction
        ):
            raise DomainError(
                DomainErrorCode.INVALID_VALUE_OBJECT, "Campaign objective and CTA are required"
            )
        if not isinstance(self.daily_budget, DailyBudget) or not isinstance(
            self.payload_hash, PayloadHash
        ):
            raise DomainError(
                DomainErrorCode.INVALID_VALUE_OBJECT, "Campaign requires budget and payload hash"
            )

    def _with_transition(self, state: CampaignState) -> "CampaignDraft":
        transitioned = replace(self)
        object.__setattr__(transitioned, "state", state)
        object.__setattr__(transitioned, "version", self.version + 1)
        return transitioned


@dataclass(frozen=True)
class ApprovalRequest:
    approval_id: UUID
    seller_id: UUID
    campaign_id: UUID
    payload_hash: PayloadHash
    requested_at: datetime
    expires_at: datetime
    status: ApprovalStatus = field(default=ApprovalStatus.PENDING, init=False)
    approved_by: UUID | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        _require_uuid(self.approval_id, "approval_id")
        _require_uuid(self.seller_id, "seller_id")
        _require_uuid(self.campaign_id, "campaign_id")
        _require_aware_datetime(self.requested_at, "requested_at")
        _require_aware_datetime(self.expires_at, "expires_at")
        if self.expires_at <= self.requested_at:
            raise DomainError(
                DomainErrorCode.INVALID_APPROVAL, "Approval must expire after it is requested"
            )

    def _approved_by(self, approver_id: UUID) -> "ApprovalRequest":
        _require_uuid(approver_id, "approver_id")
        approved = replace(self)
        object.__setattr__(approved, "status", ApprovalStatus.APPROVED)
        object.__setattr__(approved, "approved_by", approver_id)
        return approved


@dataclass(frozen=True)
class CampaignExecution:
    execution_id: UUID
    seller_id: UUID
    campaign_id: UUID
    approval_id: UUID
    idempotency_key: str
    requested_at: datetime

    def __post_init__(self) -> None:
        _require_uuid(self.execution_id, "execution_id")
        _require_uuid(self.seller_id, "seller_id")
        _require_uuid(self.campaign_id, "campaign_id")
        _require_uuid(self.approval_id, "approval_id")
        _require_text(self.idempotency_key, "idempotency_key")
        _require_aware_datetime(self.requested_at, "requested_at")


@dataclass(frozen=True)
class PerformanceSnapshot:
    snapshot_id: UUID
    seller_id: UUID
    campaign_id: UUID
    observed_at: datetime
    spend: Money
    orders: int

    def __post_init__(self) -> None:
        _require_uuid(self.snapshot_id, "snapshot_id")
        _require_uuid(self.seller_id, "seller_id")
        _require_uuid(self.campaign_id, "campaign_id")
        _require_aware_datetime(self.observed_at, "observed_at")
        if (
            not isinstance(self.spend, Money)
            or isinstance(self.orders, bool)
            or not isinstance(self.orders, int)
            or self.orders < 0
        ):
            raise DomainError(
                DomainErrorCode.INVALID_VALUE_OBJECT, "Snapshot requires valid spend and orders"
            )


@dataclass(frozen=True)
class Recommendation:
    recommendation_id: UUID
    seller_id: UUID
    campaign_id: UUID
    reason_code: str
    created_at: datetime

    def __post_init__(self) -> None:
        _require_uuid(self.recommendation_id, "recommendation_id")
        _require_uuid(self.seller_id, "seller_id")
        _require_uuid(self.campaign_id, "campaign_id")
        _require_text(self.reason_code, "reason_code")
        _require_aware_datetime(self.created_at, "created_at")


@dataclass(frozen=True)
class IdempotencyRecord:
    seller_id: UUID
    key: str
    payload_hash: PayloadHash
    expires_at: datetime

    def __post_init__(self) -> None:
        _require_uuid(self.seller_id, "seller_id")
        _require_text(self.key, "key")
        _require_aware_datetime(self.expires_at, "expires_at")


@dataclass(frozen=True)
class AuditEvent:
    event_id: UUID
    seller_id: UUID
    actor_id: UUID
    action: str
    resource_id: UUID
    occurred_at: datetime
    payload_hash: PayloadHash | None = None

    def __post_init__(self) -> None:
        _require_uuid(self.event_id, "event_id")
        _require_uuid(self.seller_id, "seller_id")
        _require_uuid(self.actor_id, "actor_id")
        _require_uuid(self.resource_id, "resource_id")
        _require_text(self.action, "action")
        _require_aware_datetime(self.occurred_at, "occurred_at")
