"""P07 tenant, permission, request-validation, and transaction-boundary tests."""

from collections.abc import AsyncIterator
from typing import cast
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx2 import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from marketing_ai.api.dependencies import get_session
from marketing_ai.api.v1.meta_connections import (
    get_connect_service,
    get_disconnect_service,
    get_list_service,
)
from marketing_ai.application.meta.connect import StartedConnection
from marketing_ai.application.meta.list_connections import MetaConnectionSummary
from marketing_ai.core.config import Settings
from tests.api.test_authentication import signed_identity


class Session:
    commits = 0

    async def commit(self) -> None:
        self.commits += 1


@pytest.mark.anyio
async def test_meta_routes_require_authenticated_manager(
    client: AsyncClient, settings: Settings
) -> None:
    assert (await client.get("/meta/connections")).status_code == 401
    viewer = signed_identity(settings, roles=["ads_viewer"])
    assert (
        await client.post(
            "/meta/connections/start",
            json={"session_id": "00000000-0000-0000-0000-000000000099", "scopes": ["ads_read"]},
            headers={"Authorization": f"Bearer {viewer}"},
        )
    ).status_code == 403


@pytest.mark.anyio
async def test_meta_start_validates_required_identifiers_and_scopes(
    app: FastAPI, client: AsyncClient, settings: Settings
) -> None:
    # Schema validation is tested with the secure service dependency overridden;
    # production still correctly rejects a missing vault with a controlled 503.
    app.dependency_overrides[get_connect_service] = lambda: object()
    try:
        manager = signed_identity(settings, roles=["ads_manager"])
        headers = {"Authorization": f"Bearer {manager}"}
        assert (
            await client.post(
                "/meta/connections/start", json={"scopes": ["ads_read"]}, headers=headers
            )
        ).status_code == 422
        assert (
            await client.post(
                "/meta/connections/start",
                json={"session_id": str(uuid4()), "scopes": []},
                headers=headers,
            )
        ).status_code == 422
        assert (
            await client.post(
                "/meta/connections/start",
                json={"session_id": str(uuid4()), "scopes": [""]},
                headers=headers,
            )
        ).status_code == 422
    finally:
        app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_meta_routes_pass_only_verified_seller_scope_and_commit_local_changes(
    app: FastAPI, client: AsyncClient, settings: Settings
) -> None:
    session = Session()
    seller_a, seller_b = uuid4(), uuid4()
    observed: list[UUID] = []

    class Connect:
        async def start(self, *, seller_id: UUID, **kwargs: object) -> StartedConnection:
            observed.append(seller_id)
            return StartedConnection(uuid4(), "signed-state")

    class List:
        async def execute(self, seller_id: UUID) -> tuple[MetaConnectionSummary, ...]:
            observed.append(seller_id)
            return ()

    class Disconnect:
        async def revoke_local(self, *, seller_id: UUID, **kwargs: object) -> str:
            observed.append(seller_id)
            return "opaque-reference"

        def revoke_credential(self, reference: str) -> None:
            assert reference == "opaque-reference"

    async def session_override() -> AsyncIterator[AsyncSession]:
        yield cast(AsyncSession, session)

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[get_connect_service] = lambda: Connect()
    app.dependency_overrides[get_list_service] = lambda: List()
    app.dependency_overrides[get_disconnect_service] = lambda: Disconnect()
    try:
        manager_a = signed_identity(settings, roles=["ads_manager"], seller_id=str(seller_a))
        reader_a = signed_identity(settings, roles=["ads_viewer"], seller_id=str(seller_a))
        manager_b = signed_identity(settings, roles=["ads_manager"], seller_id=str(seller_b))
        headers_a = {"Authorization": f"Bearer {manager_a}"}
        started = await client.post(
            "/meta/connections/start",
            json={"session_id": str(uuid4()), "scopes": ["ads_read"]},
            headers=headers_a,
        )
        assert started.status_code == 201
        assert "opaque-reference" not in started.text
        assert session.commits == 1
        assert (
            await client.get("/meta/connections", headers={"Authorization": f"Bearer {reader_a}"})
        ).json() == []
        assert (
            await client.delete(
                f"/meta/connections/{uuid4()}", headers={"Authorization": f"Bearer {manager_b}"}
            )
        ).status_code == 204
        assert observed == [seller_a, seller_a, seller_b]
        assert session.commits == 2
    finally:
        app.dependency_overrides.clear()
