"""Real PostgreSQL lifecycle, isolation, replay, and revocation tests for P07."""

import asyncio
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import select
from sqlalchemy.engine import URL

from marketing_ai.application.meta.connect import ConnectMeta
from marketing_ai.application.meta.disconnect import DisconnectMeta
from marketing_ai.core.config import Settings
from marketing_ai.core.errors import ApplicationError, ErrorCode
from marketing_ai.infrastructure.crypto.token_vault import InMemoryTestTokenVault, OAuthStateSigner
from marketing_ai.infrastructure.database.models.meta import (
    MetaAdAccountLinkModel,
)
from marketing_ai.infrastructure.database.repositories.meta_connections import (
    MetaConnectionRepository,
)
from marketing_ai.infrastructure.database.session import Database

pytestmark = [pytest.mark.database, pytest.mark.anyio]
ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def db_settings(settings_values: dict[str, Any], postgres_url: URL) -> Settings:
    return Settings(
        _env_file=None,
        **(settings_values | {"DATABASE_URL": postgres_url.render_as_string(hide_password=False)}),
    )


@pytest.fixture
def migrated_database(
    db_settings: Settings,
    settings_values: dict[str, Any],
    postgres_url: URL,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Iterator[Database]:
    for key, value in (
        settings_values | {"DATABASE_URL": postgres_url.render_as_string(hide_password=False)}
    ).items():
        monkeypatch.setenv(key, str(value))
    monkeypatch.chdir(tmp_path)
    ini = tmp_path / "alembic.ini"
    ini.write_text(f"[alembic]\nscript_location = {ROOT / 'migrations'}\npath_separator = os\n")
    command.upgrade(Config(str(ini)), "head")
    database = Database(db_settings)
    try:
        yield database
    finally:
        asyncio.run(database.close())


async def start_connection(
    database: Database, *, seller_id: UUID, vault: InMemoryTestTokenVault
) -> tuple[ConnectMeta, str, UUID]:
    now = datetime.now(UTC)
    async with database.session() as session:
        service = ConnectMeta(
            repository=MetaConnectionRepository(session),
            vault=vault,
            state_signer=OAuthStateSigner("p07-db-state-secret", 60),
            platform_currency="MAD",
        )
        started = await service.start(
            seller_id=seller_id, session_id=uuid4(), scopes=("ads_read",), now=now
        )
        await session.commit()
    return service, started.state, started.connection_id


async def complete_connection(
    database: Database,
    *,
    seller_id: UUID,
    state: str,
    vault: InMemoryTestTokenVault,
    account_id: str,
) -> ErrorCode | None:
    now = datetime.now(UTC)
    async with database.session() as session:
        service = ConnectMeta(
            repository=MetaConnectionRepository(session),
            vault=vault,
            state_signer=OAuthStateSigner("p07-db-state-secret", 60),
            platform_currency="MAD",
        )
        try:
            await service.complete(
                seller_id=seller_id,
                state=state,
                access_token="credential-canary",
                external_user_id="external-user",
                expires_at=now + timedelta(hours=1),
                account_id=account_id,
                account_currency="MAD",
                now=now,
            )
            await session.commit()
        except ApplicationError as exc:
            await session.rollback()
            return exc.code
    return None


async def test_repository_enforces_tenant_scope_and_persists_only_reference(
    migrated_database: Database,
) -> None:
    seller_a, seller_b = uuid4(), uuid4()
    vault = InMemoryTestTokenVault()
    _, state, connection_id = await start_connection(
        migrated_database, seller_id=seller_a, vault=vault
    )
    assert (
        await complete_connection(
            migrated_database,
            seller_id=seller_a,
            state=state,
            vault=vault,
            account_id="act_123",
        )
        is None
    )

    async with migrated_database.session() as session:
        repository = MetaConnectionRepository(session)
        owned = await repository.get(seller_id=seller_a, connection_id=connection_id)
        assert owned is not None
        assert owned.status == "CONNECTED"
        assert owned.credential_reference is not None
        assert "credential-canary" not in owned.credential_reference
        assert await repository.get(seller_id=seller_b, connection_id=connection_id) is None
        assert await repository.list(seller_id=seller_b) == ()


async def test_replayed_concurrent_callback_has_one_winner_and_one_active_link(
    migrated_database: Database,
) -> None:
    seller_id = uuid4()
    vault = InMemoryTestTokenVault()
    _, state, connection_id = await start_connection(
        migrated_database, seller_id=seller_id, vault=vault
    )
    results = await asyncio.gather(
        complete_connection(
            migrated_database,
            seller_id=seller_id,
            state=state,
            vault=vault,
            account_id="act_replay",
        ),
        complete_connection(
            migrated_database,
            seller_id=seller_id,
            state=state,
            vault=vault,
            account_id="act_replay",
        ),
    )
    assert results.count(None) == 1
    assert results.count(ErrorCode.STATE_CONFLICT) == 1
    assert len(vault._values) == 1
    async with migrated_database.session() as session:
        connection = await MetaConnectionRepository(session).get(
            seller_id=seller_id, connection_id=connection_id
        )
        links = list(
            await session.scalars(
                select(MetaAdAccountLinkModel).where(
                    MetaAdAccountLinkModel.connection_id == connection_id
                )
            )
        )
        assert connection is not None and connection.status == "CONNECTED"
        assert len(links) == 1 and links[0].is_active


async def test_disconnect_commits_local_revocation_before_vault_failure(
    migrated_database: Database,
) -> None:
    class FailingVault(InMemoryTestTokenVault):
        def revoke(self, reference: str) -> None:
            raise RuntimeError("synthetic vault outage")

    seller_id = uuid4()
    vault = FailingVault()
    _, state, connection_id = await start_connection(
        migrated_database, seller_id=seller_id, vault=vault
    )
    assert (
        await complete_connection(
            migrated_database,
            seller_id=seller_id,
            state=state,
            vault=vault,
            account_id="act_disconnect",
        )
        is None
    )
    async with migrated_database.session() as session:
        service = DisconnectMeta(MetaConnectionRepository(session), vault)
        reference = await service.revoke_local(
            seller_id=seller_id, connection_id=connection_id, now=datetime.now(UTC)
        )
        await session.commit()
        service.revoke_credential(reference)
    async with migrated_database.session() as session:
        model = await MetaConnectionRepository(session).get(
            seller_id=seller_id, connection_id=connection_id
        )
        link = await session.scalar(
            select(MetaAdAccountLinkModel).where(
                MetaAdAccountLinkModel.connection_id == connection_id
            )
        )
        assert model is not None and model.status == "REVOKED" and model.revoked_at is not None
        assert link is not None and not link.is_active
