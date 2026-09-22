"""Replaceable verification adapter for signed Maroc Affiliate identities.

This core boundary verifies a constrained HS256 JWT contract and returns a
framework-independent Principal. It does not authorize actions, persist users,
or expose token contents. A future identity adapter implements IdentityVerifier
without changing domain identity or application authorization code.
"""

import base64
import binascii
import hashlib
import hmac
import json
import math
import time
from collections.abc import Callable, Mapping
from typing import Never, Protocol
from uuid import UUID

from marketing_ai.domain.identity.permissions import Permission, Role
from marketing_ai.domain.identity.principal import Principal


class IdentityVerificationError(Exception):
    """Safe internal signal for any missing, malformed, or invalid identity."""


class IdentityVerifier(Protocol):
    """Narrow adapter port used by HTTP and worker identity entry points."""

    def verify(self, token: str) -> Principal: ...


def _reject() -> Never:
    raise IdentityVerificationError("Identity verification failed")


def _decode_base64url(segment: str) -> bytes:
    try:
        padding = "=" * (-len(segment) % 4)
        decoded = base64.urlsafe_b64decode((segment + padding).encode("ascii"))
    except UnicodeEncodeError, binascii.Error:
        _reject()
    canonical = base64.urlsafe_b64encode(decoded).rstrip(b"=").decode("ascii")
    if not hmac.compare_digest(segment, canonical):
        _reject()
    return decoded


def _decode_json(segment: str) -> Mapping[str, object]:
    try:
        value = json.loads(_decode_base64url(segment), object_pairs_hook=_unique_object)
    except UnicodeDecodeError, json.JSONDecodeError, ValueError:
        _reject()
    if not isinstance(value, dict):
        _reject()
    return value


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            _reject()
        result[key] = value
    return result


def _uuid_claim(claims: Mapping[str, object], name: str) -> UUID:
    value = claims.get(name)
    if not isinstance(value, str):
        _reject()
    try:
        return UUID(value)
    except ValueError:
        _reject()


def _claim_values(claims: Mapping[str, object], name: str) -> tuple[str, ...]:
    value = claims.get(name, [])
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        _reject()
    values = tuple(value)
    if len(set(values)) != len(values):
        _reject()
    return values


class HmacSha256IdentityVerifier:
    """Default signer adapter; HS256 is fixed to prevent algorithm confusion."""

    def __init__(
        self,
        *,
        issuer: str,
        audience: str,
        signing_secret: str,
        now: Callable[[], float] = time.time,
    ) -> None:
        if not issuer or not audience or not signing_secret:
            raise ValueError("Identity verifier requires issuer, audience, and signing secret")
        self._issuer = issuer
        self._audience = audience
        self._signing_secret = signing_secret.encode("utf-8")
        self._now = now

    def verify(self, token: str) -> Principal:
        if not isinstance(token, str):
            _reject()
        parts = token.split(".")
        if len(parts) != 3 or any(not part for part in parts):
            _reject()
        encoded_header, encoded_claims, encoded_signature = parts
        header = _decode_json(encoded_header)
        if header.get("alg") != "HS256" or ("typ" in header and header.get("typ") != "JWT"):
            _reject()
        supplied_signature = _decode_base64url(encoded_signature)
        expected_signature = hmac.digest(
            self._signing_secret,
            f"{encoded_header}.{encoded_claims}".encode("ascii"),
            hashlib.sha256,
        )
        if not hmac.compare_digest(expected_signature, supplied_signature):
            _reject()

        claims = _decode_json(encoded_claims)
        if claims.get("iss") != self._issuer or not self._has_expected_audience(claims.get("aud")):
            _reject()
        expires_at = claims.get("exp")
        if isinstance(expires_at, bool) or not isinstance(expires_at, int | float):
            _reject()
        try:
            is_expired = not math.isfinite(expires_at) or expires_at <= self._now()
        except OverflowError:
            _reject()
        if is_expired:
            _reject()

        user_id = _uuid_claim(claims, "sub")
        if "user_id" in claims and _uuid_claim(claims, "user_id") != user_id:
            _reject()
        seller_id = _uuid_claim(claims, "seller_id")
        try:
            roles = frozenset(Role(value) for value in _claim_values(claims, "roles"))
            permissions = frozenset(
                Permission(value) for value in _claim_values(claims, "permissions")
            )
        except ValueError:
            _reject()
        platform_admin = claims.get("is_platform_admin", False)
        if not isinstance(platform_admin, bool):
            _reject()
        return Principal(
            user_id=user_id,
            seller_id=seller_id,
            roles=roles,
            permissions=permissions,
            is_platform_admin=platform_admin,
        )

    def _has_expected_audience(self, value: object) -> bool:
        if isinstance(value, str):
            return value == self._audience
        if isinstance(value, list) and all(isinstance(item, str) for item in value):
            return any(item == self._audience for item in value)
        return False
