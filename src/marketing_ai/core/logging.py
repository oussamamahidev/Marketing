"""Allowlisted runtime events and per-request context; no raw payload logging.

Used by middleware/lifespan/readiness. Formatters deliberately omit arbitrary
messages, args, exceptions and extras. Tests cover secrets and concurrency.
"""

import json
import logging
import math
import sys
from contextvars import ContextVar

request_id_context: ContextVar[str | None] = ContextVar("request_id", default=None)
correlation_id_context: ContextVar[str | None] = ContextVar("correlation_id", default=None)

EVENTS = frozenset(
    {
        "service_started",
        "service_stopped",
        "http_request_complete",
        "http_request_failed",
        "http_request_cancelled",
        "readiness_check_complete",
        "readiness_check_failed",
        "database_transaction_committed",
        "database_transaction_failed",
        "database_transaction_cancelled",
    }
)


class SafeFormatter(logging.Formatter):
    def __init__(self, *, json_output: bool) -> None:
        super().__init__()
        self.json_output = json_output

    def format(self, record: logging.LogRecord) -> str:
        event = (
            record.msg if isinstance(record.msg, str) and record.msg in EVENTS else "external_log"
        )
        fields: dict[str, str | int | float | None] = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "event": event,
            "request_id": request_id_context.get(),
            "correlation_id": correlation_id_context.get(),
        }
        for key in ("status_code", "duration_ms"):
            value = getattr(record, key, None)
            if type(value) is int or (type(value) is float and math.isfinite(value)):
                fields[key] = value
        if self.json_output:
            return json.dumps(fields, ensure_ascii=True, allow_nan=False)
        return " ".join(f"{key}={value}" for key, value in fields.items())


def configure_logging(*, environment: str, level: str) -> None:
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(SafeFormatter(json_output=environment != "local"))
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
    for name in ("uvicorn", "uvicorn.error"):
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.propagate = True
    # Raw Uvicorn access lines include request targets/query strings.
    logging.getLogger("uvicorn.access").disabled = True
