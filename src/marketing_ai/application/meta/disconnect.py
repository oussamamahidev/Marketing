"""Immediate local revocation before best-effort credential-vault revocation."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from marketing_ai.core.errors import ApplicationError, ErrorCode
from marketing_ai.infrastructure.crypto.token_vault import TokenVault
from marketing_ai.infrastructure.database.repositories.meta_connections import (
    MetaConnectionRepository,
)


class DisconnectMeta:
    def __init__(self, repository: MetaConnectionRepository, vault: TokenVault) -> None:
        self._repository = repository
        self._vault = vault

    async def revoke_local(
        self, *, seller_id: UUID, connection_id: UUID, now: datetime
    ) -> str | None:
        model = await self._repository.get(
            seller_id=seller_id, connection_id=connection_id, lock_for_update=True
        )
        if model is None:
            raise ApplicationError(ErrorCode.RESOURCE_NOT_FOUND)
        reference = model.credential_reference
        await self._repository.revoke(model=model, now=now)
        return reference

    def revoke_credential(self, reference: str | None) -> None:
        if reference:
            try:
                self._vault.revoke(reference)
            except Exception:
                pass

    async def execute(self, *, seller_id: UUID, connection_id: UUID, now: datetime) -> None:
        self.revoke_credential(
            await self.revoke_local(seller_id=seller_id, connection_id=connection_id, now=now)
        )
