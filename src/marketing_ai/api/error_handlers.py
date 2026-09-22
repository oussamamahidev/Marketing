"""Translate errors to the canonical safe HTTP envelope, including outer 500s."""

from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse

from marketing_ai.core.errors import (
    ApplicationError,
    ErrorCode,
    ErrorDetail,
    ErrorLocation,
    ErrorReason,
)

ERRORS: dict[ErrorCode, tuple[int, str]] = {
    ErrorCode.INVALID_REQUEST: (400, "Invalid request"),
    ErrorCode.VALIDATION_FAILED: (422, "Request validation failed"),
    ErrorCode.UNAUTHENTICATED: (401, "Authentication required"),
    ErrorCode.FORBIDDEN: (403, "Action is not permitted"),
    ErrorCode.RESOURCE_NOT_FOUND: (404, "Resource not found"),
    ErrorCode.METHOD_NOT_ALLOWED: (405, "Method not allowed"),
    ErrorCode.STATE_CONFLICT: (409, "Resource state conflicts with this request"),
    ErrorCode.RATE_LIMITED: (429, "Request limit reached"),
    ErrorCode.UPSTREAM_INVALID_RESPONSE: (502, "Invalid upstream response"),
    ErrorCode.DEPENDENCY_UNAVAILABLE: (503, "Required dependency is unavailable"),
    ErrorCode.UPSTREAM_TIMEOUT: (504, "Upstream request timed out"),
    ErrorCode.INTERNAL_ERROR: (500, "Internal server error"),
}


def error_response(request: Request, error: ApplicationError) -> JSONResponse:
    status, message = ERRORS[error.code]
    request_id = getattr(request.state, "request_id", None) or str(uuid4())
    correlation_id = getattr(request.state, "correlation_id", None) or request_id
    return JSONResponse(
        status_code=status,
        content={
            "error": {
                "code": error.code.value,
                "message": message,
                "details": [
                    {"location": detail.location.value, "reason": detail.reason.value}
                    for detail in error.details
                ],
            },
            "request_id": request_id,
        },
        headers={"X-Request-ID": request_id, "X-Correlation-ID": correlation_id},
    )


async def handle_application_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, ApplicationError)
    return error_response(request, exc)


async def handle_http_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, HTTPException)
    code = next(
        (code for code, (status, _) in ERRORS.items() if status == exc.status_code),
        ErrorCode.INTERNAL_ERROR,
    )
    response = error_response(request, ApplicationError(code))
    if exc.status_code == 405 and exc.headers:
        methods = [method.strip() for method in exc.headers.get("Allow", "").split(",")]
        if methods and all(
            method in {"GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"}
            for method in methods
        ):
            response.headers["Allow"] = ", ".join(methods)
    return response


async def handle_validation_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    details = []
    for error in exc.errors():
        raw_location = error.get("loc", ("request",))[0]
        location = (
            ErrorLocation(raw_location) if raw_location in ErrorLocation else ErrorLocation.REQUEST
        )
        reason = ErrorReason.REQUIRED if error.get("type") == "missing" else ErrorReason.INVALID
        details.append(ErrorDetail(location, reason))
    return error_response(request, ApplicationError(ErrorCode.VALIDATION_FAILED, details=details))


async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    return error_response(request, ApplicationError(ErrorCode.INTERNAL_ERROR))


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ApplicationError, handle_application_error)
    app.add_exception_handler(HTTPException, handle_http_error)
    app.add_exception_handler(RequestValidationError, handle_validation_error)
    app.add_exception_handler(Exception, handle_unexpected_error)
