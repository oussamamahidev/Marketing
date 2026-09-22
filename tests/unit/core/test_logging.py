"""Formatting allowlist prevents raw messages, headers, prompts and traces leaking."""

import asyncio
import json
import logging
from io import StringIO
from typing import cast

import pytest
from starlette.types import Message, Scope

from marketing_ai.api.middleware import RequestContextMiddleware
from marketing_ai.core.errors import (
    ApplicationError,
    ErrorCode,
    ErrorDetail,
    ErrorLocation,
    ErrorReason,
)
from marketing_ai.core.logging import (
    SafeFormatter,
    configure_logging,
    correlation_id_context,
    request_id_context,
)


@pytest.mark.parametrize("environment", ["local", "test", "staging", "production"])
def test_environment_selects_log_format(environment: str, monkeypatch: pytest.MonkeyPatch) -> None:
    output = StringIO()
    monkeypatch.setattr("sys.stderr", output)
    configure_logging(environment=environment, level="INFO")
    logging.getLogger(__name__).info("service_started")
    if environment == "local":
        assert "event=service_started" in output.getvalue()
    else:
        assert json.loads(output.getvalue())["event"] == "service_started"


@pytest.mark.parametrize("json_output", [False, True])
def test_formatter_discards_sensitive_text_and_extras(json_output: bool) -> None:
    canary = "p02-authorization-token-customer-prompt-canary"
    record = logging.LogRecord("library", logging.ERROR, __file__, 1, "%s", (canary,), None)
    record.authorization = canary
    record.prompt = canary
    record.exc_info = (ValueError, ValueError(canary), None)
    record.duration_ms = float("nan")
    formatted = SafeFormatter(json_output=json_output).format(record)
    assert canary not in formatted
    assert "external_log" in formatted
    if json_output:
        assert json.loads(formatted)["event"] == "external_log"


def test_formatter_includes_request_context() -> None:
    request_token = request_id_context.set("test-request")
    correlation_token = correlation_id_context.set("test-correlation")
    try:
        record = logging.LogRecord(
            "app", logging.INFO, __file__, 1, "http_request_complete", (), None
        )
        output = json.loads(SafeFormatter(json_output=True).format(record))
        assert output["request_id"] == "test-request"
        assert output["correlation_id"] == "test-correlation"
    finally:
        request_id_context.reset(request_token)
        correlation_id_context.reset(correlation_token)


@pytest.mark.anyio
async def test_cancellation_clears_context() -> None:
    async def downstream(scope: Scope, receive: object, send: object) -> None:
        assert request_id_context.get() is not None
        raise asyncio.CancelledError

    async def receive() -> Message:
        return {"type": "http.request", "body": b""}

    async def send(message: Message) -> None:
        raise AssertionError("Cancelled request should not create a success response")

    middleware = RequestContextMiddleware(downstream)
    with pytest.raises(asyncio.CancelledError):
        await middleware({"type": "http", "headers": []}, receive, send)
    assert request_id_context.get() is None
    assert correlation_id_context.get() is None


@pytest.mark.parametrize("value", [float("inf"), float("-inf"), float("nan"), "p02-secret", True])
def test_log_extras_cannot_smuggle_non_numeric_or_nonfinite_values(value: object) -> None:
    record = logging.LogRecord("app", logging.INFO, __file__, 1, "http_request_complete", (), None)
    record.duration_ms = value
    record.status_code = value
    output = json.loads(SafeFormatter(json_output=True).format(record))
    assert "duration_ms" not in output and "status_code" not in output


def test_errors_reject_uncontrolled_codes_and_details() -> None:
    with pytest.raises(ValueError):
        ApplicationError(cast(ErrorCode, "p02-raw-provider-secret"))
    with pytest.raises(ValueError):
        ApplicationError(
            ErrorCode.INVALID_REQUEST,
            details=[ErrorDetail(ErrorLocation.BODY, cast(ErrorReason, "p02-secret"))],
        )
    detail = ErrorDetail(ErrorLocation.BODY, ErrorReason.INVALID)
    error = ApplicationError(ErrorCode.INVALID_REQUEST, details=[detail])
    assert error.details == (detail,)


@pytest.mark.anyio
async def test_non_http_scope_passes_through_without_request_context() -> None:
    observed = []

    async def downstream(scope: Scope, receive: object, send: object) -> None:
        observed.append(scope["type"])
        assert request_id_context.get() is None

    async def receive() -> Message:
        return {"type": "lifespan.startup"}

    async def send(message: Message) -> None:
        pass

    await RequestContextMiddleware(downstream)({"type": "lifespan"}, receive, send)
    assert observed == ["lifespan"]
