"""Thin tenant-scoped Meta connection lifecycle HTTP handlers."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from marketing_ai.api.dependencies import (
    get_seller_context,
    get_session,
    get_settings,
    require_permission,
)
from marketing_ai.application.meta.connect import ConnectMeta
from marketing_ai.application.meta.disconnect import DisconnectMeta
from marketing_ai.application.meta.list_connections import (
    ListMetaConnections,
    MetaConnectionSummary,
)
from marketing_ai.core.config import Settings
from marketing_ai.core.errors import ApplicationError, ErrorCode
from marketing_ai.domain.identity.permissions import Permission
from marketing_ai.domain.identity.principal import SellerContext
from marketing_ai.infrastructure.crypto.token_vault import OAuthStateSigner, TokenVault
from marketing_ai.infrastructure.database.repositories.meta_connections import (
    MetaConnectionRepository,
)

router = APIRouter(prefix="/meta/connections", tags=["meta"])
Scope = Annotated[str, Field(min_length=1)]


class StartBody(BaseModel):
    session_id: UUID
    scopes: tuple[Scope, ...] = Field(min_length=1)


class ConnectionOut(BaseModel):
    connection_id: UUID
    status: str
    scopes: tuple[str, ...]
    expires_at: datetime | None
    created_at: datetime


async def get_token_vault(request: Request) -> TokenVault:
    """Resolve the deployment-provided vault without accepting a token in a route."""
    vault = getattr(request.app.state, "meta_token_vault", None)
    if not callable(getattr(vault, "store", None)) or not callable(getattr(vault, "revoke", None)):
        raise ApplicationError(ErrorCode.DEPENDENCY_UNAVAILABLE)
    return cast(TokenVault, vault)


def get_state_signer(settings: Settings) -> OAuthStateSigner:
    secret = settings.META_OAUTH_STATE_SIGNING_SECRET
    ttl_seconds = settings.META_OAUTH_STATE_TTL_SECONDS
    if secret is None or ttl_seconds is None:
        raise ApplicationError(ErrorCode.DEPENDENCY_UNAVAILABLE)
    return OAuthStateSigner(secret.get_secret_value(), ttl_seconds)


async def get_connect_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    vault: Annotated[TokenVault, Depends(get_token_vault)],
) -> ConnectMeta:
    return ConnectMeta(
        repository=MetaConnectionRepository(session),
        vault=vault,
        state_signer=get_state_signer(settings),
        platform_currency=settings.PLATFORM_CURRENCY,
    )


async def get_disconnect_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    vault: Annotated[TokenVault, Depends(get_token_vault)],
) -> DisconnectMeta:
    return DisconnectMeta(MetaConnectionRepository(session), vault)


async def get_list_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ListMetaConnections:
    return ListMetaConnections(MetaConnectionRepository(session))


@router.post("/start", status_code=status.HTTP_201_CREATED)
async def start(
    body: StartBody,
    _: Annotated[object, Depends(require_permission(Permission.ADS_MANAGE))],
    context: Annotated[SellerContext, Depends(get_seller_context)],
    service: Annotated[ConnectMeta, Depends(get_connect_service)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, str]:
    result = await service.start(
        seller_id=context.seller_id,
        session_id=body.session_id,
        scopes=body.scopes,
        now=datetime.now(UTC),
    )
    await session.commit()
    return {"connection_id": str(result.connection_id), "state": result.state}


@router.get("", response_model=tuple[ConnectionOut, ...])
async def list_connections(
    _: Annotated[object, Depends(require_permission(Permission.ADS_READ))],
    context: Annotated[SellerContext, Depends(get_seller_context)],
    service: Annotated[ListMetaConnections, Depends(get_list_service)],
) -> tuple[MetaConnectionSummary, ...]:
    return await service.execute(context.seller_id)


@router.delete("/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect(
    connection_id: UUID,
    _: Annotated[object, Depends(require_permission(Permission.ADS_MANAGE))],
    context: Annotated[SellerContext, Depends(get_seller_context)],
    service: Annotated[DisconnectMeta, Depends(get_disconnect_service)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    reference = await service.revoke_local(
        seller_id=context.seller_id, connection_id=connection_id, now=datetime.now(UTC)
    )
    await session.commit()
    service.revoke_credential(reference)
