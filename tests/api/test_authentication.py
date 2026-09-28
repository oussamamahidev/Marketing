"""HTTP authentication boundary tests for P04."""

import base64
import hashlib
import hmac
import json
import time
from typing import Annotated, Any

import pytest
from fastapi import Depends, FastAPI
from httpx2 import AsyncClient

from marketing_ai.api.dependencies import get_seller_context, require_permission
from marketing_ai.core.config import Settings
from marketing_ai.domain.identity.permissions import Permission
from marketing_ai.domain.identity.principal import Principal, SellerContext

USER_ID = "00000000-0000-0000-0000-000000000001"
SELLER_ID = "00000000-0000-0000-0000-000000000010"

pytestmark = pytest.mark.anyio


def compact_json(value: object) -> str:
    return (
        base64.urlsafe_b64encode(
            json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
        )
        .rstrip(b"=")
        .decode("ascii")
    )


def signed_identity(settings: Settings, **changes: object) -> str:
    claims: dict[str, object] = {
        "iss": settings.IDENTITY_JWT_ISSUER,
        "aud": settings.IDENTITY_JWT_AUDIENCE,
        "sub": USER_ID,
        "seller_id": SELLER_ID,
        "roles": ["ads_manager"],
        "permissions": [],
        "exp": time.time() + 60,
    }
    claims.update(changes)
    header = compact_json({"alg": "HS256", "typ": "JWT"})
    payload = compact_json(claims)
    signature = hmac.digest(
        settings.IDENTITY_JWT_HS256_SECRET.get_secret_value().encode(),
        f"{header}.{payload}".encode("ascii"),
        hashlib.sha256,
    )
    return f"{header}.{payload}.{base64.urlsafe_b64encode(signature).rstrip(b'=').decode('ascii')}"


def protected_endpoint(app: FastAPI) -> None:
    @app.get("/_p04/protected")
    async def protected(
        principal: Annotated[Principal, Depends(require_permission(Permission.ADS_MANAGE))],
        context: Annotated[SellerContext, Depends(get_seller_context)],
    ) -> dict[str, str]:
        return {"user_id": str(principal.user_id), "seller_id": str(context.seller_id)}


async def test_verified_identity_populates_principal_and_seller_context(
    app: FastAPI, client: AsyncClient, settings: Settings
) -> None:
    protected_endpoint(app)
    response = await client.get(
        "/_p04/protected", headers={"Authorization": f"Bearer {signed_identity(settings)}"}
    )
    assert response.status_code == 200
    assert response.json() == {"user_id": USER_ID, "seller_id": SELLER_ID}


@pytest.mark.parametrize(
    "header",
    [
        None,
        "Basic irrelevant",
        "Bearer malformed.identity",
    ],
)
async def test_missing_or_malformed_identity_is_unauthenticated(
    app: FastAPI, client: AsyncClient, header: str | None
) -> None:
    protected_endpoint(app)
    headers = {} if header is None else {"Authorization": header}
    response = await client.get("/_p04/protected", headers=headers)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"
    assert header is None or header not in response.text


@pytest.mark.parametrize(
    "changes",
    [
        {"exp": time.time() - 1},
        {"iss": "untrusted-issuer"},
        {"aud": "wrong-audience"},
        {"roles": ["unknown-role"]},
        {"seller_id": "not-a-uuid"},
    ],
)
async def test_expired_or_invalid_signed_identity_is_unauthenticated(
    app: FastAPI, client: AsyncClient, settings: Settings, changes: dict[str, object]
) -> None:
    protected_endpoint(app)
    token = signed_identity(settings, **changes)
    response = await client.get("/_p04/protected", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"
    assert token not in response.text


async def test_invalid_signature_and_algorithm_confusion_are_rejected(
    app: FastAPI, client: AsyncClient, settings: Settings
) -> None:
    protected_endpoint(app)
    valid = signed_identity(settings)
    signature_tampered = valid[:-1] + ("a" if valid[-1] != "a" else "b")
    header = compact_json({"alg": "none", "typ": "JWT"})
    _, payload, signature = valid.split(".")
    confused = f"{header}.{payload}.{signature}"
    for token in (signature_tampered, confused):
        response = await client.get("/_p04/protected", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "UNAUTHENTICATED"
        assert token not in response.text


async def test_authenticated_but_unauthorized_identity_is_forbidden(
    app: FastAPI, client: AsyncClient, settings: Settings
) -> None:
    protected_endpoint(app)
    viewer = signed_identity(settings, roles=["ads_viewer"])
    response = await client.get("/_p04/protected", headers={"Authorization": f"Bearer {viewer}"})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"

    # The explicit platform-admin flag is retained for audited later use; it does not bypass scope.
    platform_admin = signed_identity(settings, roles=[], is_platform_admin=True)
    response = await client.get(
        "/_p04/protected", headers={"Authorization": f"Bearer {platform_admin}"}
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_identity_settings_are_required_and_signing_secret_is_not_serialized(
    settings_values: dict[str, Any],
) -> None:
    canary = "p04-secret-never-display"
    configured = Settings(
        _env_file=None, **(settings_values | {"IDENTITY_JWT_HS256_SECRET": canary})
    )
    assert canary not in repr(configured)
    assert canary not in configured.model_dump_json()
    assert "IDENTITY_JWT_HS256_SECRET" not in configured.model_dump()
    for field in ("IDENTITY_JWT_ISSUER", "IDENTITY_JWT_AUDIENCE", "IDENTITY_JWT_HS256_SECRET"):
        values = settings_values.copy()
        values.pop(field)
        with pytest.raises(Exception):
            Settings(_env_file=None, **values)


async def test_malformed_verifier_response_fails_closed_as_unauthenticated(
    app: FastAPI, client: AsyncClient, settings: Settings
) -> None:
    """A replaceable adapter cannot broaden access by returning an arbitrary object."""
    from typing import cast

    from marketing_ai.api.dependencies import get_identity_verifier

    class MalformedVerifier:
        def verify(self, token: str) -> Principal:
            return cast(Principal, object())

    app.dependency_overrides[get_identity_verifier] = lambda: MalformedVerifier()
    protected_endpoint(app)
    response = await client.get(
        "/_p04/protected", headers={"Authorization": f"Bearer {signed_identity(settings)}"}
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"


async def test_admin_capability_is_explicit_not_inferred_from_manager_role(
    app: FastAPI, client: AsyncClient, settings: Settings
) -> None:
    @app.get("/_p04/admin")
    async def admin_only(
        principal: Annotated[Principal, Depends(require_permission(Permission.ADS_ADMIN))],
    ) -> dict[str, str]:
        return {"user_id": str(principal.user_id)}

    manager = signed_identity(settings, roles=["ads_manager"])
    denied = await client.get("/_p04/admin", headers={"Authorization": f"Bearer {manager}"})
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "FORBIDDEN"

    admin = signed_identity(settings, roles=["ads_admin"])
    allowed = await client.get("/_p04/admin", headers={"Authorization": f"Bearer {admin}"})
    assert allowed.status_code == 200


@pytest.mark.parametrize(
    "changes",
    [
        {"user_id": "00000000-0000-0000-0000-000000000099"},
        {"roles": ["ads_viewer", "ads_viewer"]},
        {"permissions": ["ads.read", "ads.read"]},
        {"permissions": "ads.manage"},
        {"is_platform_admin": 1},
        {"aud": []},
    ],
)
async def test_invalid_identity_claim_shapes_fail_closed(
    app: FastAPI, client: AsyncClient, settings: Settings, changes: dict[str, object]
) -> None:
    protected_endpoint(app)
    token = signed_identity(settings, **changes)
    response = await client.get("/_p04/protected", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"
    assert token not in response.text


async def test_audience_array_and_direct_permission_claim_are_valid(
    app: FastAPI, client: AsyncClient, settings: Settings
) -> None:
    protected_endpoint(app)
    token = signed_identity(
        settings,
        aud=["unrelated-service", settings.IDENTITY_JWT_AUDIENCE],
        roles=[],
        permissions=["ads.manage"],
    )
    response = await client.get("/_p04/protected", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200


async def test_duplicate_json_claim_and_raw_token_are_not_accepted_or_logged(
    app: FastAPI, client: AsyncClient, settings: Settings, capsys: pytest.CaptureFixture[str]
) -> None:
    protected_endpoint(app)
    header = compact_json({"alg": "HS256", "typ": "JWT"})
    raw_claims = (
        '{"iss":"untrusted","iss":"'
        + settings.IDENTITY_JWT_ISSUER
        + '","aud":"'
        + settings.IDENTITY_JWT_AUDIENCE
        + '","sub":"'
        + USER_ID
        + '","seller_id":"'
        + SELLER_ID
        + '","roles":[],"permissions":[],"exp":9999999999}'
    )
    payload = base64.urlsafe_b64encode(raw_claims.encode()).rstrip(b"=").decode("ascii")
    signature = hmac.digest(
        settings.IDENTITY_JWT_HS256_SECRET.get_secret_value().encode(),
        f"{header}.{payload}".encode("ascii"),
        hashlib.sha256,
    )
    token = f"{header}.{payload}.{base64.urlsafe_b64encode(signature).rstrip(b'=').decode('ascii')}"
    response = await client.get("/_p04/protected", headers={"Authorization": f"Bearer {token}"})
    captured = capsys.readouterr()
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"
    assert token not in response.text + captured.out + captured.err
