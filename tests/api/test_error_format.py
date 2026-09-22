"""Error normalization and request isolation; routes exist only inside tests."""

import asyncio
import json
from io import StringIO
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI, HTTPException
from httpx2 import ASGITransport, AsyncClient
from pydantic import BaseModel

from marketing_ai.core.errors import ApplicationError, ErrorCode
from marketing_ai.core.logging import configure_logging, correlation_id_context, request_id_context

pytestmark = pytest.mark.anyio


@pytest.mark.parametrize("status", [400, 401, 403, 404, 405, 409, 422, 429, 502, 503, 504])
async def test_http_errors_are_safe_and_correlated(
    app: FastAPI, client: AsyncClient, status: int
) -> None:
    async def endpoint() -> None:
        raise HTTPException(status, detail={"token": "p02-error-secret"})

    app.add_api_route("/test/error", endpoint)
    request_id, correlation_id = str(uuid4()), str(uuid4())
    response = await client.get(
        "/test/error",
        headers={
            "X-Request-ID": request_id,
            "X-Correlation-ID": correlation_id,
        },
    )
    assert response.status_code == status
    body = response.json()
    assert set(body) == {"error", "request_id"}
    assert set(body["error"]) == {"code", "message", "details"}
    assert body["request_id"] == response.headers["x-request-id"] == request_id
    assert response.headers["x-correlation-id"] == correlation_id
    assert "p02-error-secret" not in response.text


async def test_unhandled_error_keeps_envelope_and_headers(app: FastAPI) -> None:
    async def endpoint() -> None:
        raise RuntimeError("p02-unhandled-secret")

    app.add_api_route("/test/crash", endpoint)
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app, raise_app_exceptions=False), base_url="http://testserver"
        ) as client:
            response = await client.get("/test/crash")
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert response.json()["request_id"] == response.headers["x-request-id"]
    assert "p02-unhandled-secret" not in response.text
    assert request_id_context.get() is None


async def test_application_error_and_unknown_route_use_same_shape(
    app: FastAPI, client: AsyncClient
) -> None:
    async def endpoint() -> None:
        raise ApplicationError(ErrorCode.STATE_CONFLICT)

    app.add_api_route("/test/conflict", endpoint)
    assert (await client.get("/test/conflict")).json()["error"]["code"] == "STATE_CONFLICT"
    response = await client.get("/unknown")
    assert response.status_code == 404
    assert response.json()["request_id"] == response.headers["x-request-id"]


class Payload(BaseModel):
    count: int


@pytest.mark.parametrize(
    "payload", ['{"count":"p02-body-secret"}', "{invalid-json", "{}", "null", "[]"]
)
async def test_request_validation_never_echoes_input(
    app: FastAPI, client: AsyncClient, payload: str
) -> None:
    async def endpoint(payload: Payload) -> dict[str, int]:
        return {"count": payload.count}

    app.add_api_route("/test/validate", endpoint, methods=["POST"])
    response = await client.post(
        "/test/validate", content=payload, headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_FAILED"
    assert response.json()["error"]["details"]
    assert "p02-body-secret" not in response.text and "invalid-json" not in response.text


@pytest.mark.parametrize("header", ["X-Request-ID", "X-Correlation-ID"])
@pytest.mark.parametrize("incoming", ["", "unsafe id", "x" * 4096, "bad\r\nHeader: value"])
async def test_unsafe_request_ids_are_replaced(
    client: AsyncClient, incoming: str, header: str
) -> None:
    response = await client.get("/health/live", headers={header: incoming})
    assert str(UUID(response.headers[header])) == response.headers[header]
    assert response.headers[header] != incoming


@pytest.mark.parametrize("header", ["X-Request-ID", "X-Correlation-ID"])
async def test_duplicate_header_is_not_trusted(client: AsyncClient, header: str) -> None:
    value = str(uuid4())
    response = await client.get("/health/live", headers=[(header, value), (header, value)])
    assert response.headers[header] != value


async def test_real_method_error_keeps_allow_header(client: AsyncClient) -> None:
    response = await client.post("/health/live")
    assert response.status_code == 405
    assert response.json()["error"]["code"] == "METHOD_NOT_ALLOWED"
    assert "GET" in response.headers["allow"]


async def test_request_logs_are_correlated_without_sensitive_inputs(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = StringIO()
    monkeypatch.setattr("sys.stderr", output)
    configure_logging(environment="test", level="INFO")
    request_id = str(uuid4())
    secret = "p02-query-authorization-secret"
    response = await client.get(
        "/unknown?token=" + secret,
        headers={"X-Request-ID": request_id, "Authorization": "Bearer " + secret},
    )
    logs = output.getvalue()
    assert response.status_code == 404
    assert request_id in logs
    assert "http_request_complete" in logs
    assert secret not in logs


async def test_concurrent_request_context_is_isolated(app: FastAPI, client: AsyncClient) -> None:
    async def endpoint() -> dict[str, str | None]:
        before = request_id_context.get()
        await asyncio.sleep(0)
        return {
            "before": before,
            "after": request_id_context.get(),
            "correlation": correlation_id_context.get(),
        }

    app.add_api_route("/test/context", endpoint)
    ids = [str(uuid4()) for _ in range(8)]
    responses = await asyncio.gather(
        *(client.get("/test/context", headers={"X-Request-ID": value}) for value in ids)
    )
    for expected, response in zip(ids, responses, strict=True):
        assert response.json() == {"before": expected, "after": expected, "correlation": expected}
    assert request_id_context.get() is None
    assert correlation_id_context.get() is None


@pytest.mark.parametrize("header", ["X-Request-ID", "X-Correlation-ID"])
@pytest.mark.parametrize("value", ["z" * 36, "12345678_1234_1234_1234_123456789012"])
async def test_uuid_shaped_invalid_headers_are_replaced(
    client: AsyncClient, header: str, value: str
) -> None:
    response = await client.get("/health/live", headers={header: value})
    assert str(UUID(response.headers[header])) == response.headers[header]
    assert response.headers[header] != value


async def test_success_ids_are_normalized_and_new_requests_get_fresh_ids(
    client: AsyncClient,
) -> None:
    request_id, correlation_id = str(uuid4()), str(uuid4())
    response = await client.get(
        "/health/live",
        headers={"X-Request-ID": request_id.upper(), "X-Correlation-ID": correlation_id.upper()},
    )
    assert response.headers["x-request-id"] == request_id
    assert response.headers["x-correlation-id"] == correlation_id
    following = [await client.get("/health/live") for _ in range(2)]
    assert len({request_id, *(item.headers["x-request-id"] for item in following)}) == 3
    for item in following:
        assert item.headers["x-correlation-id"] == item.headers["x-request-id"]


async def test_invalid_response_schema_is_safe_and_correlated(app: FastAPI) -> None:
    async def endpoint() -> dict[str, str]:
        return {"count": "p02-response-secret"}

    app.add_api_route("/test/bad-response", endpoint, response_model=Payload)
    request_id, correlation_id = str(uuid4()), str(uuid4())
    async with AsyncClient(
        transport=ASGITransport(app, raise_app_exceptions=False), base_url="http://testserver"
    ) as client:
        response = await client.get(
            "/test/bad-response",
            headers={"X-Request-ID": request_id, "X-Correlation-ID": correlation_id},
        )
    assert response.status_code == 500
    assert response.json()["error"] == {
        "code": "INTERNAL_ERROR",
        "message": "Internal server error",
        "details": [],
    }
    assert response.json()["request_id"] == response.headers["x-request-id"] == request_id
    assert response.headers["x-correlation-id"] == correlation_id
    assert "p02-response-secret" not in response.text


async def test_failed_request_does_not_leak_secret_or_context_to_next_request(
    app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def endpoint() -> None:
        raise RuntimeError("p02-stacktrace-token-secret")

    app.add_api_route("/test/failed", endpoint)
    output = StringIO()
    monkeypatch.setattr("sys.stderr", output)
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app, raise_app_exceptions=False), base_url="http://testserver"
        ) as client:
            first = await client.get("/test/failed")
            second = await client.get("/health/live")
    assert first.status_code == 500 and second.status_code == 200
    assert first.headers["x-request-id"] != second.headers["x-request-id"]
    assert "p02-stacktrace-token-secret" not in output.getvalue()
    events = [json.loads(line) for line in output.getvalue().splitlines()]
    failure = next(event for event in events if event["event"] == "http_request_failed")
    assert failure["request_id"] == first.headers["x-request-id"]
    assert request_id_context.get() is None and correlation_id_context.get() is None


async def test_query_and_path_errors_do_not_echo_invalid_identifiers(
    app: FastAPI, client: AsyncClient
) -> None:
    async def endpoint(resource_id: int, page: int) -> None:
        return None

    app.add_api_route("/test/resources/{resource_id}", endpoint)
    response = await client.get("/test/resources/p02-private-identifier?page=p02-private-query")
    assert response.status_code == 422
    assert {detail["location"] for detail in response.json()["error"]["details"]} == {
        "path",
        "query",
    }
    assert "p02-private" not in response.text
