"""Token vault abstractions and signed OAuth state.

PURPOSE: keep Meta credential plaintext outside ordinary application storage.
RESPONSIBILITY: store opaque references and sign/verify short-lived state; no HTTP or database access.
DEPENDENCIES: Python standard library only.
USED BY: Meta connection application services.
TESTED BY: tests/unit/meta/test_token_vault.py.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import UUID


class TokenVault(Protocol):
    def store(self, plaintext: str) -> str: ...

    def revoke(self, reference: str) -> None: ...


class EnvelopeEncryptor(Protocol):
    def encrypt(self, plaintext: bytes) -> bytes: ...


class SecretManager(Protocol):
    def put(self, ciphertext: bytes) -> str: ...

    def revoke(self, reference: str) -> None: ...


@dataclass
class EnvelopeTokenVault:
    """Production composition: a KMS envelope encryptor plus a secret manager."""

    encryptor: EnvelopeEncryptor
    secret_manager: SecretManager

    def store(self, plaintext: str) -> str:
        if not isinstance(plaintext, str) or not plaintext:
            raise ValueError("Token vault accepts non-empty credential text")
        return self.secret_manager.put(self.encryptor.encrypt(plaintext.encode("utf-8")))

    def revoke(self, reference: str) -> None:
        self.secret_manager.revoke(reference)


@dataclass
class InMemoryTestTokenVault:
    """Explicit test-only vault; production must compose EnvelopeTokenVault."""

    _values: dict[str, str] = field(default_factory=dict, repr=False)

    def store(self, plaintext: str) -> str:
        if not isinstance(plaintext, str) or not plaintext:
            raise ValueError("Token vault accepts non-empty credential text")
        reference = "test-vault/" + secrets.token_urlsafe()
        self._values[reference] = plaintext
        return reference

    def revoke(self, reference: str) -> None:
        self._values.pop(reference, None)


@dataclass(frozen=True)
class OAuthState:
    seller_id: UUID
    session_id: UUID
    connection_id: UUID
    expires_at: datetime


class OAuthStateSigner:
    def __init__(self, secret: str, ttl_seconds: int) -> None:
        if (
            not isinstance(secret, str)
            or not secret
            or not isinstance(ttl_seconds, int)
            or ttl_seconds <= 0
        ):
            raise ValueError("OAuth state signer requires secret and positive TTL")
        self._secret = secret.encode("utf-8")
        self._ttl_seconds = ttl_seconds

    def issue(
        self, *, seller_id: UUID, session_id: UUID, connection_id: UUID, now: datetime
    ) -> str:
        if not all(isinstance(value, UUID) for value in (seller_id, session_id, connection_id)):
            raise ValueError("OAuth state identifiers must be UUIDs")
        if now.tzinfo is None:
            raise ValueError("OAuth state time must be timezone-aware")
        expires_at = now + timedelta(seconds=self._ttl_seconds)
        payload = json.dumps(
            {
                "seller_id": str(seller_id),
                "session_id": str(session_id),
                "connection_id": str(connection_id),
                "exp": int(expires_at.timestamp()),
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        encoded = base64.urlsafe_b64encode(payload).rstrip(b"=")
        signature = hmac.digest(self._secret, encoded, hashlib.sha256)
        return encoded.decode() + "." + base64.urlsafe_b64encode(signature).rstrip(b"=").decode()

    def verify(self, state: str, *, now: datetime) -> OAuthState:
        try:
            encoded, signature = state.split(".")
            expected = hmac.digest(self._secret, encoded.encode(), hashlib.sha256)
            padding = "=" * (-len(signature) % 4)
            supplied = base64.urlsafe_b64decode(signature + padding)
            padding = "=" * (-len(encoded) % 4)
            payload = json.loads(base64.urlsafe_b64decode(encoded + padding))
            parsed = OAuthState(
                seller_id=UUID(payload["seller_id"]),
                session_id=UUID(payload["session_id"]),
                connection_id=UUID(payload["connection_id"]),
                expires_at=datetime.fromtimestamp(payload["exp"], UTC),
            )
        except ValueError, KeyError, TypeError, json.JSONDecodeError:
            raise ValueError("Invalid OAuth state") from None
        if (
            now.tzinfo is None
            or not hmac.compare_digest(supplied, expected)
            or now >= parsed.expires_at
        ):
            raise ValueError("Invalid OAuth state")
        return parsed
