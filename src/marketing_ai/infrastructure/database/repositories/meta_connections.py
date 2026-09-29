"""Tenant-scoped persistence for Meta connection lifecycle records."""

from __future__ import annotations

from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from marketing_ai.infrastructure.database.models.meta import (
    MetaAdAccountLinkModel,
    MetaConnectionModel,
)


class MetaConnectionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add_pending(self, model: MetaConnectionModel) -> None:
        self._session.add(model)
        await self._session.flush()

    async def get(
        self, *, seller_id: UUID, connection_id: UUID, lock_for_update: bool = False
    ) -> MetaConnectionModel | None:
        statement = select(MetaConnectionModel).where(
            MetaConnectionModel.seller_id == seller_id,
            MetaConnectionModel.connection_id == connection_id,
        )
        if lock_for_update:
            statement = statement.with_for_update()
        return cast(
            MetaConnectionModel | None,
            await self._session.scalar(statement),
        )

    async def list(self, *, seller_id: UUID) -> tuple[MetaConnectionModel, ...]:
        return tuple(
            (
                await self._session.scalars(
                    select(MetaConnectionModel)
                    .where(MetaConnectionModel.seller_id == seller_id)
                    .order_by(MetaConnectionModel.created_at.desc())
                )
            ).all()
        )

    async def connect(
        self,
        *,
        model: MetaConnectionModel,
        credential_reference: str,
        external_user_id: str,
        expires_at: datetime,
        account_id: str,
        currency: str,
        now: datetime,
    ) -> None:
        model.status = "CONNECTED"
        model.credential_reference = credential_reference
        model.external_user_id = external_user_id
        model.expires_at = expires_at
        model.oauth_state_digest = None
        model.oauth_state_expires_at = None
        model.updated_at = now
        self._session.add(
            MetaAdAccountLinkModel(
                connection_id=model.connection_id,
                seller_id=model.seller_id,
                external_account_id=account_id,
                currency=currency,
                is_active=True,
                created_at=now,
            )
        )
        await self._session.flush()

    async def revoke(self, *, model: MetaConnectionModel, now: datetime) -> None:
        model.status = "REVOKED"
        model.revoked_at = now
        model.updated_at = now
        await self._session.execute(
            update(MetaAdAccountLinkModel)
            .where(MetaAdAccountLinkModel.connection_id == model.connection_id)
            .values(is_active=False)
        )
        await self._session.flush()
