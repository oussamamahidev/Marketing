"""Framework-independent error vocabulary; presentation translates to HTTP.

Messages and details are controlled values, never raw exception/provider text.
Tested through tests/api/test_error_format.py.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum


class ErrorCode(StrEnum):
    INVALID_REQUEST = "INVALID_REQUEST"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    UNAUTHENTICATED = "UNAUTHENTICATED"
    FORBIDDEN = "FORBIDDEN"
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    METHOD_NOT_ALLOWED = "METHOD_NOT_ALLOWED"
    STATE_CONFLICT = "STATE_CONFLICT"
    RATE_LIMITED = "RATE_LIMITED"
    UPSTREAM_INVALID_RESPONSE = "UPSTREAM_INVALID_RESPONSE"
    DEPENDENCY_UNAVAILABLE = "DEPENDENCY_UNAVAILABLE"
    UPSTREAM_TIMEOUT = "UPSTREAM_TIMEOUT"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class ErrorLocation(StrEnum):
    BODY = "body"
    QUERY = "query"
    PATH = "path"
    HEADER = "header"
    COOKIE = "cookie"
    REQUEST = "request"


class ErrorReason(StrEnum):
    REQUIRED = "Required value is missing"
    INVALID = "Invalid value"


@dataclass(frozen=True)
class ErrorDetail:
    location: ErrorLocation
    reason: ErrorReason


class ApplicationError(Exception):
    def __init__(self, code: ErrorCode, *, details: Sequence[ErrorDetail] = ()) -> None:
        if not isinstance(code, ErrorCode) or any(
            not isinstance(detail, ErrorDetail)
            or not isinstance(detail.location, ErrorLocation)
            or not isinstance(detail.reason, ErrorReason)
            for detail in details
        ):
            raise ValueError("Application errors require controlled codes and details")
        self.code = code
        self.details = tuple(details)
        super().__init__(code.value)
