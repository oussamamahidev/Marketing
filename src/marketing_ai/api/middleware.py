"""HTTP request context with canonical UUID headers and cancellation-safe reset."""

import asyncio
import logging
from time import perf_counter
from uuid import UUID, uuid4

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from marketing_ai.core.logging import correlation_id_context, request_id_context

logger = logging.getLogger(__name__)


def safe_id(headers: Headers, name: str) -> str | None:
    values = headers.getlist(name)
    if len(values) != 1:
        return None
    value = values[0]
    # A UUID's canonical grammar bounds input without adding a business limit.
    if len(value) != len(str(UUID(int=0))):
        return None
    try:
        normalized = str(UUID(value))
    except ValueError:
        return None
    return normalized if normalized == value.lower() else None


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = Headers(scope=scope)
        request_id = safe_id(headers, "x-request-id") or str(uuid4())
        correlation_id = safe_id(headers, "x-correlation-id") or request_id
        state = scope.setdefault("state", {})
        state.update(request_id=request_id, correlation_id=correlation_id)
        request_token = request_id_context.set(request_id)
        correlation_token = correlation_id_context.set(correlation_id)
        started = perf_counter()
        status_code = 500

        async def send_with_context(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                outgoing = MutableHeaders(scope=message)
                outgoing["X-Request-ID"] = request_id
                outgoing["X-Correlation-ID"] = correlation_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_context)
        except asyncio.CancelledError:
            logger.info("http_request_cancelled")
            raise
        except Exception:
            logger.error("http_request_failed", extra={"status_code": 500})
            raise
        else:
            logger.info(
                "http_request_complete",
                extra={
                    "status_code": status_code,
                    "duration_ms": (perf_counter() - started) * 1000,
                },
            )
        finally:
            request_id_context.reset(request_token)
            correlation_id_context.reset(correlation_token)
