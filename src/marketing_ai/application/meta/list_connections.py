"""Safe tenant-scoped Meta connection projections."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from marketing_ai.infrastructure.database.repositories.meta_connections import (
    MetaConnectionRepository,
)


@dataclass(frozen=True)
class MetaConnectionSummary:
    connection_id: UUID
    status: str
    scopes: tuple[str, ...]
    expires_at: datetime | None
    created_at: datetime


class ListMetaConnections:
    def __init__(self, repository: MetaConnectionRepository) -> None:
        self._repository = repository

    async def execute(self, seller_id: UUID) -> tuple[MetaConnectionSummary, ...]:
        return tuple(
            MetaConnectionSummary(
                x.connection_id, x.status, tuple(x.scopes), x.expires_at, x.created_at
            )
            for x in await self._repository.list(seller_id=seller_id)
        )
