"""Safe, bounded transport for seller-scoped internal read integrations.

PURPOSE: centralize read-only HTTP mechanics and safe error translation.
RESPONSIBILITY: issue bounded GET requests; never expose raw response data or credentials.
DEPENDENCIES: core errors, Prometheus, httpx2, and Python standard library.
USED BY: Catalog, Inventory, Orders, and Content Hub clients.
TESTED BY: tests/contract/internal/test_*_contract.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from types import MappingProxyType
from typing import TYPE_CHECKING, Mapping
from urllib.parse import urlsplit
from uuid import UUID

import httpx2
from prometheus_client import Counter, Histogram

from marketing_ai.core.errors import ApplicationError, ErrorCode

READS = Counter(
    "marketing_ai_internal_reads_total",
    "Internal read adapter outcomes",
    ["service", "outcome"],
)
READ_DURATION = Histogram(
    "marketing_ai_internal_read_duration_seconds",
    "Internal read adapter latency",
    ["service", "outcome"],
)


@dataclass(frozen=True)
class InternalReadClientConfig:
    base_url: str
    service_identity: str
    timeout_seconds: int
    max_retries: int

    def __post_init__(self) -> None:
        if not isinstance(self.base_url, str):
            raise ValueError("Internal read client requires a credential-free HTTP origin")
        parsed = urlsplit(self.base_url)
        if (
            not isinstance(self.base_url, str)
            or parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("Internal read client requires a credential-free HTTP origin")
        if not isinstance(self.service_identity, str) or not self.service_identity.strip():
            raise ValueError("Internal read client requires a service identity")
        if isinstance(self.timeout_seconds, bool) or not isinstance(self.timeout_seconds, int):
            raise ValueError("Internal read client timeout must be a positive integer")
        if self.timeout_seconds <= 0:
            raise ValueError("Internal read client timeout must be positive")
        if isinstance(self.max_retries, bool) or not isinstance(self.max_retries, int):
            raise ValueError("Internal read retry bound must be a non-negative integer")
        if self.max_retries < 0:
            raise ValueError("Internal read retry bound must be non-negative")


class ReadOnlyInternalClient:
    """Transport shared by narrow clients; retries only safe GET requests."""

    def __init__(
        self,
        *,
        service: str,
        config: InternalReadClientConfig,
        http_client: httpx2.AsyncClient,
    ) -> None:
        if not isinstance(service, str) or not service:
            raise ValueError("Integration service name is required")
        self._service = service
        self._config = config
        self._http_client = http_client

    async def get_json(self, *, seller_id: UUID, path: str) -> Mapping[str, object]:
        if not isinstance(seller_id, UUID) or not path.startswith("/"):
            raise ValueError("Seller-scoped integration reads require UUID and absolute path")
        started = perf_counter()
        attempts = self._config.max_retries + 1
        for attempt in range(attempts):
            try:
                response = await self._http_client.get(
                    self._config.base_url + path,
                    headers={
                        "Accept": "application/json",
                        "X-Seller-ID": str(seller_id),
                        "X-Service-Identity": self._config.service_identity,
                    },
                    timeout=self._config.timeout_seconds,
                    follow_redirects=False,
                )
            except httpx2.TimeoutException:
                if attempt + 1 == attempts:
                    self._record("timeout", started)
                    raise ApplicationError(ErrorCode.UPSTREAM_TIMEOUT) from None
                continue
            except httpx2.RequestError:
                if attempt + 1 == attempts:
                    self._record("unavailable", started)
                    raise ApplicationError(ErrorCode.DEPENDENCY_UNAVAILABLE) from None
                continue

            if response.status_code >= 500:
                if attempt + 1 == attempts:
                    self._record("unavailable", started)
                    raise ApplicationError(ErrorCode.DEPENDENCY_UNAVAILABLE) from None
                continue
            if response.status_code == 404:
                self._record("not_found", started)
                raise ApplicationError(ErrorCode.RESOURCE_NOT_FOUND)
            if response.status_code in {401, 403}:
                self._record("forbidden", started)
                raise ApplicationError(ErrorCode.FORBIDDEN)
            if response.status_code == 429:
                self._record("rate_limited", started)
                raise ApplicationError(ErrorCode.RATE_LIMITED)
            if response.status_code < 200 or response.status_code >= 300:
                self._record("invalid_response", started)
                raise ApplicationError(ErrorCode.UPSTREAM_INVALID_RESPONSE)
            try:
                payload = response.json()
            except ValueError:
                self._record("invalid_response", started)
                raise ApplicationError(ErrorCode.UPSTREAM_INVALID_RESPONSE) from None
            if not isinstance(payload, dict):
                self._record("invalid_response", started)
                raise ApplicationError(ErrorCode.UPSTREAM_INVALID_RESPONSE)
            self._record("success", started)
            return MappingProxyType(payload)
        raise AssertionError("Bounded retry loop must return or raise")

    def _record(self, outcome: str, started: float) -> None:
        READS.labels(service=self._service, outcome=outcome).inc()
        READ_DURATION.labels(service=self._service, outcome=outcome).observe(
            perf_counter() - started
        )


def ensure_seller_scope(*, requested_seller_id: UUID, resource_seller_id: UUID) -> None:
    """Hide foreign resource existence just as a scoped repository lookup does."""
    if requested_seller_id != resource_seller_id:
        raise ApplicationError(ErrorCode.RESOURCE_NOT_FOUND)


def read_client_config_from_settings(
    *, settings: "Settings", base_url: str | None
) -> InternalReadClientConfig:
    """Build transport input only when the typed application settings are complete."""
    from marketing_ai.core.config import ConfigurationError

    if (
        base_url is None
        or settings.INTERNAL_SERVICE_IDENTITY is None
        or settings.INTERNAL_READ_TIMEOUT_SECONDS is None
        or settings.INTERNAL_READ_MAX_RETRIES is None
    ):
        raise ConfigurationError("Internal read client configuration is incomplete")
    return InternalReadClientConfig(
        base_url=base_url,
        service_identity=settings.INTERNAL_SERVICE_IDENTITY.get_secret_value(),
        timeout_seconds=settings.INTERNAL_READ_TIMEOUT_SECONDS,
        max_retries=settings.INTERNAL_READ_MAX_RETRIES,
    )


if TYPE_CHECKING:
    from marketing_ai.core.config import Settings
