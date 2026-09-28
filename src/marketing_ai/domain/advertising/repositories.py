"""Seller-scoped persistence ports for advertising aggregates.

PURPOSE: let application code depend on narrow domain interfaces.
RESPONSIBILITY: declare tenant-scoped operations; no database implementation or transaction handling.
DEPENDENCIES: Python typing and advertising domain entities.
USED BY: application use cases and later infrastructure adapters.
TESTED BY: architecture/import checks; concrete adapters are tested when introduced.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from marketing_ai.domain.advertising.entities import (
    ApprovalRequest,
    AuditEvent,
    CampaignDraft,
    CampaignExecution,
    IdempotencyRecord,
    PerformanceSnapshot,
    Recommendation,
    SellerMarketingProfile,
)


class SellerMarketingProfileRepository(Protocol):
    async def get(self, seller_id: UUID) -> SellerMarketingProfile | None: ...


class CampaignDraftRepository(Protocol):
    async def get(self, seller_id: UUID, campaign_id: UUID) -> CampaignDraft | None: ...

    async def save(self, campaign: CampaignDraft, expected_version: int) -> CampaignDraft: ...


class ApprovalRequestRepository(Protocol):
    async def get(self, seller_id: UUID, approval_id: UUID) -> ApprovalRequest | None: ...

    async def save(self, request: ApprovalRequest) -> ApprovalRequest: ...


class CampaignExecutionRepository(Protocol):
    async def get(self, seller_id: UUID, execution_id: UUID) -> CampaignExecution | None: ...

    async def save(self, execution: CampaignExecution) -> CampaignExecution: ...


class PerformanceSnapshotRepository(Protocol):
    async def append(self, snapshot: PerformanceSnapshot) -> None: ...

    async def list_for_campaign(
        self, seller_id: UUID, campaign_id: UUID, observed_after: datetime
    ) -> tuple[PerformanceSnapshot, ...]: ...


class RecommendationRepository(Protocol):
    async def save(self, recommendation: Recommendation) -> Recommendation: ...


class IdempotencyRecordRepository(Protocol):
    async def get(self, seller_id: UUID, key: str) -> IdempotencyRecord | None: ...

    async def save(self, record: IdempotencyRecord) -> IdempotencyRecord: ...


class AuditEventRepository(Protocol):
    async def append(self, event: AuditEvent) -> None: ...
