"""Server-side start/complete lifecycle for a seller-scoped Meta connection."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from marketing_ai.core.errors import ApplicationError, ErrorCode
from marketing_ai.infrastructure.crypto.token_vault import OAuthStateSigner, TokenVault
from marketing_ai.infrastructure.database.models.meta import MetaConnectionModel
from marketing_ai.infrastructure.database.repositories.meta_connections import (
    MetaConnectionRepository,
)


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


@dataclass(frozen=True)
class StartedConnection:
    connection_id: UUID
    state: str


class ConnectMeta:
    def __init__(
        self,
        *,
        repository: MetaConnectionRepository,
        vault: TokenVault,
        state_signer: OAuthStateSigner,
        platform_currency: str,
    ) -> None:
        self._repository = repository
        self._vault = vault
        self._state_signer = state_signer
        self._platform_currency = platform_currency

    async def start(
        self, *, seller_id: UUID, session_id: UUID, scopes: tuple[str, ...], now: datetime
    ) -> StartedConnection:
        connection_id = uuid4()
        state = self._state_signer.issue(
            seller_id=seller_id, session_id=session_id, connection_id=connection_id, now=now
        )
        model = MetaConnectionModel(
            connection_id=connection_id,
            seller_id=seller_id,
            status="PENDING",
            scopes=list(scopes),
            external_user_id=None,
            credential_reference=None,
            oauth_state_digest=digest(state),
            oauth_state_expires_at=self._state_signer.verify(state, now=now).expires_at,
            expires_at=None,
            revoked_at=None,
            created_at=now,
            updated_at=now,
        )
        await self._repository.add_pending(model)
        return StartedConnection(connection_id, state)

    async def complete(
        self,
        *,
        seller_id: UUID,
        state: str,
        access_token: str,
        external_user_id: str,
        expires_at: datetime,
        account_id: str,
        account_currency: str,
        now: datetime,
    ) -> UUID:
        try:
            parsed = self._state_signer.verify(state, now=now)
        except ValueError:
            raise ApplicationError(ErrorCode.STATE_CONFLICT) from None
        if parsed.seller_id != seller_id:
            raise ApplicationError(ErrorCode.RESOURCE_NOT_FOUND)
        model = await self._repository.get(
            seller_id=seller_id, connection_id=parsed.connection_id, lock_for_update=True
        )
        if (
            model is None
            or model.status != "PENDING"
            or model.oauth_state_digest != digest(state)
            or model.oauth_state_expires_at is None
            or now >= model.oauth_state_expires_at
        ):
            raise ApplicationError(ErrorCode.STATE_CONFLICT)
        if account_currency != self._platform_currency:
            raise ApplicationError(ErrorCode.VALIDATION_FAILED)
        reference = self._vault.store(access_token)
        try:
            await self._repository.connect(
                model=model,
                credential_reference=reference,
                external_user_id=external_user_id,
                expires_at=expires_at,
                account_id=account_id,
                currency=account_currency,
                now=now,
            )
        except Exception:
            try:
                self._vault.revoke(reference)
            except Exception:
                pass
            raise
        return model.connection_id
