"""Actual ASGI/lifespan health behavior, including bounded injected failures."""

import asyncio
from typing import cast

import pytest
from fastapi import FastAPI
from httpx2 import AsyncClient

from marketing_ai.api.dependencies import ReadinessProbe
from marketing_ai.core.config import Settings
from marketing_ai.core.errors import ApplicationError, ErrorCode
from marketing_ai.main import create_app

pytestmark = pytest.mark.anyio


async def test_health_with_explicit_empty_test_registry(app: FastAPI, client: AsyncClient) -> None:
    # P03's real default PostgreSQL registration is covered by database integration tests.
    assert app.state.readiness_probes[0].name == "postgresql"
    app.state.readiness_probes = ()
    assert (await client.get("/health/live")).json() == {"status": "alive"}
    assert (await client.get("/health/ready")).json() == {"status": "ready"}


@pytest.mark.parametrize("failure", ["false", "malformed", "exception", "timeout"])
async def test_readiness_fails_closed_but_liveness_remains_independent(
    app: FastAPI,
    client: AsyncClient,
    failure: str,
) -> None:
    cancelled = asyncio.Event()
    called = asyncio.Event()

    async def probe() -> bool:
        called.set()
        if failure == "false":
            return False
        if failure == "malformed":
            return cast(bool, {"unsafe": "p02-provider-secret"})
        if failure == "exception":
            raise ConnectionError("p02-provider-secret")
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()
        return True

    app.state.readiness_probes = (ReadinessProbe("dependency", probe, timeout_seconds=0.01),)
    live = await client.get("/health/live")
    assert live.status_code == 200 and not called.is_set()
    response = await client.get("/health/ready")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "DEPENDENCY_UNAVAILABLE"
    assert "p02-provider-secret" not in response.text
    if failure == "timeout":
        assert cancelled.is_set()


async def test_readiness_checks_run_concurrently(app: FastAPI, client: AsyncClient) -> None:
    entered_a, entered_b = asyncio.Event(), asyncio.Event()

    async def a() -> bool:
        entered_a.set()
        await entered_b.wait()
        return True

    async def b() -> bool:
        entered_b.set()
        await entered_a.wait()
        return True

    app.state.readiness_probes = (ReadinessProbe("a", a, 1), ReadinessProbe("b", b, 1))
    response = await client.get("/health/ready")
    assert response.status_code == 200


@pytest.mark.parametrize("code", [ErrorCode.RATE_LIMITED, ErrorCode.UNAUTHENTICATED])
async def test_probe_failures_are_dependency_errors_not_caller_auth_errors(
    app: FastAPI, client: AsyncClient, code: ErrorCode
) -> None:
    async def probe() -> bool:
        raise ApplicationError(code)

    app.state.readiness_probes = (ReadinessProbe("provider", probe, 1),)
    response = await client.get("/health/ready")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "DEPENDENCY_UNAVAILABLE"


async def test_partial_readiness_failure_then_recovery(app: FastAPI, client: AsyncClient) -> None:
    healthy = False
    calls = []

    async def stable() -> bool:
        calls.append("stable")
        return True

    async def recovering() -> bool:
        calls.append("recovering")
        return healthy

    app.state.readiness_probes = (
        ReadinessProbe("a", stable, 1),
        ReadinessProbe("b", recovering, 1),
    )
    first = await client.get("/health/ready")
    assert first.status_code == 503
    assert sorted(calls) == ["recovering", "stable"]
    healthy = True
    second = await client.get("/health/ready")
    assert second.status_code == 200
    assert first.headers["x-request-id"] != second.headers["x-request-id"]
    assert len(calls) == 4  # Neither success nor failure is cached across requests.


async def test_liveness_responds_while_readiness_is_waiting(
    app: FastAPI, client: AsyncClient
) -> None:
    entered, release = asyncio.Event(), asyncio.Event()

    async def probe() -> bool:
        entered.set()
        await release.wait()
        return True

    app.state.readiness_probes = (ReadinessProbe("waiting", probe, 5),)
    task = asyncio.create_task(client.get("/health/ready"))
    try:
        async with asyncio.timeout(2):  # Test watchdog, not an application deadline.
            await entered.wait()
            assert (await client.get("/health/live")).status_code == 200
            assert not task.done()
            release.set()
            assert (await task).status_code == 200
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def test_cancelled_readiness_request_cleans_up_all_probes(
    app: FastAPI, client: AsyncClient
) -> None:
    entered = [asyncio.Event(), asyncio.Event()]
    cleaned = [asyncio.Event(), asyncio.Event()]

    async def check(index: int) -> bool:
        entered[index].set()
        try:
            await asyncio.Event().wait()
        finally:
            cleaned[index].set()
        return True

    async def a() -> bool:
        return await check(0)

    async def b() -> bool:
        return await check(1)

    app.state.readiness_probes = (ReadinessProbe("a", a, 5), ReadinessProbe("b", b, 5))
    task = asyncio.create_task(client.get("/health/ready"))
    try:
        async with asyncio.timeout(2):
            await asyncio.gather(*(event.wait() for event in entered))
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            assert all(event.is_set() for event in cleaned)
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


@pytest.mark.parametrize("timeout", [0, -1, float("nan"), float("inf")])
async def test_probe_registration_rejects_unbounded_deadlines(timeout: float) -> None:
    async def check() -> bool:
        return True

    with pytest.raises(ValueError, match="positive finite timeout"):
        ReadinessProbe("dependency", check, timeout)


async def test_duplicate_probe_names_are_rejected(settings: Settings) -> None:
    async def check() -> bool:
        return True

    probe = ReadinessProbe("duplicate", check, 1)
    with pytest.raises(ValueError, match="unique"):
        create_app(settings, readiness_probes=(probe, probe))
