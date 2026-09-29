"""P07 vault and OAuth-state security tests."""

from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import uuid4

import pytest

from marketing_ai.infrastructure.crypto.token_vault import InMemoryTestTokenVault, OAuthStateSigner


def test_test_vault_returns_only_reference_and_revokes() -> None:
    vault = InMemoryTestTokenVault()
    token = "token-canary"
    reference = vault.store(token)
    assert token not in reference and token not in repr(vault)
    vault.revoke(reference)
    assert reference not in vault._values


def test_oauth_state_rejects_forgery_and_expiry() -> None:
    signer = OAuthStateSigner("state-test-secret", 1)
    now = datetime.now(UTC)
    state = signer.issue(seller_id=uuid4(), session_id=uuid4(), connection_id=uuid4(), now=now)
    assert signer.verify(state, now=now).connection_id
    with pytest.raises(ValueError):
        signer.verify(state[:-1] + ("x" if state[-1] != "x" else "y"), now=now)
    with pytest.raises(ValueError):
        signer.verify(state, now=now + timedelta(seconds=2))


def test_envelope_vault_keeps_plaintext_out_of_secret_manager() -> None:
    from marketing_ai.infrastructure.crypto.token_vault import EnvelopeTokenVault

    class Encryptor:
        def encrypt(self, plaintext: bytes) -> bytes:
            return b"encrypted:" + plaintext[::-1]

    class Manager:
        value = b""

        def put(self, ciphertext: bytes) -> str:
            self.value = ciphertext
            return "kms-ref"

        def revoke(self, reference: str) -> None:
            pass

    manager = Manager()
    reference = EnvelopeTokenVault(Encryptor(), manager).store("token-canary")
    assert reference == "kms-ref" and b"token-canary" not in manager.value


@pytest.mark.anyio
async def test_connection_completion_rejects_replay_and_currency_before_vault_storage() -> None:
    from marketing_ai.application.meta.connect import ConnectMeta
    from marketing_ai.core.errors import ApplicationError, ErrorCode

    class Repository:
        model: Any = None

        async def add_pending(self, model: object) -> None:
            self.model = model

        async def get(
            self, *, seller_id: object, connection_id: object, **kwargs: object
        ) -> object:
            return self.model

        async def connect(self, *, model: Any, **kwargs: object) -> None:
            model.status = "CONNECTED"
            model.oauth_state_digest = None
            model.oauth_state_expires_at = None

    class Vault:
        calls = 0

        def store(self, plaintext: str) -> str:
            self.calls += 1
            return "vault-ref"

        def revoke(self, reference: str) -> None:
            pass

    now = datetime.now(UTC)
    repository = Repository()
    vault = Vault()
    signer = OAuthStateSigner("test", 60)
    service = ConnectMeta(
        repository=cast(Any, repository),
        vault=cast(Any, vault),
        state_signer=signer,
        platform_currency="MAD",
    )
    started = await service.start(
        seller_id=uuid4(), session_id=uuid4(), scopes=("ads_read",), now=now
    )
    with pytest.raises(ApplicationError) as currency:
        await service.complete(
            seller_id=repository.model.seller_id,
            state=started.state,
            access_token="secret",
            external_user_id="user",
            expires_at=now + timedelta(seconds=60),
            account_id="account",
            account_currency="USD",
            now=now,
        )
    assert currency.value.code == ErrorCode.VALIDATION_FAILED and vault.calls == 0
    await service.complete(
        seller_id=repository.model.seller_id,
        state=started.state,
        access_token="secret",
        external_user_id="user",
        expires_at=now + timedelta(seconds=60),
        account_id="account",
        account_currency="MAD",
        now=now,
    )
    with pytest.raises(ApplicationError) as replay:
        await service.complete(
            seller_id=repository.model.seller_id,
            state=started.state,
            access_token="secret",
            external_user_id="user",
            expires_at=now + timedelta(seconds=60),
            account_id="account",
            account_currency="MAD",
            now=now,
        )
    assert replay.value.code == ErrorCode.STATE_CONFLICT


@pytest.mark.anyio
async def test_disconnect_marks_local_connection_revoked_when_vault_revocation_fails() -> None:
    from marketing_ai.application.meta.disconnect import DisconnectMeta

    class Model:
        credential_reference = "vault-ref"
        status = "CONNECTED"

    class Repository:
        model = Model()

        async def get(self, *, seller_id: object, connection_id: object, **kwargs: object) -> Model:
            return self.model

        async def revoke(self, *, model: Model, now: datetime) -> None:
            model.status = "REVOKED"

    class FailingVault:
        def store(self, plaintext: str) -> str:
            return "unused"

        def revoke(self, reference: str) -> None:
            raise RuntimeError("unavailable")

    repository = Repository()
    await DisconnectMeta(repository=cast(Any, repository), vault=cast(Any, FailingVault())).execute(
        seller_id=uuid4(), connection_id=uuid4(), now=datetime.now(UTC)
    )
    assert repository.model.status == "REVOKED"


@pytest.mark.anyio
async def test_connection_failure_after_vault_store_revokes_new_reference() -> None:
    from marketing_ai.application.meta.connect import ConnectMeta

    class Repository:
        model: Any = None

        async def add_pending(self, model: object) -> None:
            self.model = model

        async def get(self, **kwargs: object) -> object:
            return self.model

        async def connect(self, **kwargs: object) -> None:
            raise RuntimeError("synthetic database failure")

    class Vault:
        revoked: list[str] = []

        def store(self, plaintext: str) -> str:
            return "vault-ref"

        def revoke(self, reference: str) -> None:
            self.revoked.append(reference)

    now = datetime.now(UTC)
    repository = Repository()
    vault = Vault()
    service = ConnectMeta(
        repository=cast(Any, repository),
        vault=cast(Any, vault),
        state_signer=OAuthStateSigner("test", 60),
        platform_currency="MAD",
    )
    started = await service.start(
        seller_id=uuid4(), session_id=uuid4(), scopes=("ads_read",), now=now
    )
    with pytest.raises(RuntimeError, match="database failure"):
        await service.complete(
            seller_id=repository.model.seller_id,
            state=started.state,
            access_token="token-canary",
            external_user_id="user",
            expires_at=now + timedelta(seconds=60),
            account_id="account",
            account_currency="MAD",
            now=now,
        )
    assert vault.revoked == ["vault-ref"]
