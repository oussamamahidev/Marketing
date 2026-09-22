# P02 testing and validation

```text
Implementation: PASS
Unit Tests: PASS
Integration Tests: PASS
Security: PASS
Architecture: PASS
Regression: PASS
Overall: PASS
```

Review date: 2026-09-20. P01's supplied testing and validation prompts passed before this implementation; its historical evidence remains in [p01-validation.md](p01-validation.md).

This report applies the supplied TESTING P02 and VALIDATION P02 prompts. The review added 61 adversarial cases, proved and fixed one exact-money conversion defect, and reran the full relevant suite. No product scope was added and no previous test was removed or weakened.

## Verification evidence

| Check | Result |
|---|---|
| `uv run --locked pytest -q` | 234 passed, 3 container cases explicitly deselected |
| `uv run --locked pytest -q -m container` | 3 passed; actual runtime build, non-root/read-only execution, HTTP startup and secret-exclusion probe build |
| `uv run --locked mypy src tests` | PASS: strict checking, 22 files, Pydantic plugin enabled |
| `uv run --locked ruff check .` | PASS |
| `uv run --locked ruff format --check .` | PASS |
| Runtime dependency lock | Updated and installed for Pydantic Settings; valid lock and deliberate metadata drift remain tested |
| Existing local setup | The implementation previously added missing P02 settings; this testing follow-up did not change `.env`, credentials, constants or running services |
| Learning documentation | [P02-configuration-logging-errors.md](../learning/P02-configuration-logging-errors.md), all 24 required sections |

The first sandboxed Docker attempt could not access the Docker socket. The subsequently authorized run executed all container tests successfully. Tests use unique temporary images and containers, no host ports and no user database volumes. Existing PostgreSQL and Redis services were preserved. No real local `.env` is copied into test build contexts.

## Acceptance criteria

| Requirement | Implementation and evidence |
|---|---|
| Typed, environment-specific settings | `Settings` validates required inputs, exact money, ranges and cross-field relationships; staging/production reject DEBUG; every required setting has a missing-value test |
| Central business configuration | `.env.example` carries the approved values; tests compare them with BUSINESS_CONSTANTS. Runtime code contains no fallback financial thresholds. Optional URLs do not initiate connections |
| Fail clearly without secrets | `load_settings()` reports field names and error types without raw inputs; `hide_input_in_errors`, excluded SecretStr fields and safe logging protect normal diagnostics |
| Structured logging | JSON outside local; readable local fields. Allowlisted events, numeric status/duration and request context only. Tests exercise format selection, raw-message/exception exclusion and actual HTTP logging |
| Request IDs | Pure ASGI middleware validates single UUID headers, generates replacements, returns both headers and resets ContextVars on success/error/cancellation; concurrent requests remain isolated |
| Canonical API errors | Application, HTTP, request validation and unexpected failures use controlled codes/messages/details and matching request IDs. Real method rejection retains a safe Allow header |
| Independent liveness | `/health/live` never runs probes; tested with failing registered checks |
| Pluggable readiness | Concurrent async probes with explicit finite deadlines; only true succeeds. False, malformed results, exceptions and timeouts yield safe 503. Empty registry yields ready |
| Architectural scope | Error vocabulary depends only on the standard library. HTTP mapping stays in API; configuration and logging are shared runtime services. No business use case, model, auth policy, Meta client or AI graph added |

## Edge-case assessment

| Case | Result / applicability |
|---|---|
| Missing resource | Unknown routes return canonical 404 without echoing path, body or authorization input |
| Invalid settings | Missing/empty/placeholder/negative/non-finite values and incompatible currency fail; budget/page/stock/backfill boundaries use named settings. Actual factory subprocesses fail on missing/invalid environment without leaking values |
| Duplicate request/header | Duplicate ID headers are replaced. Repeated requests are independent reads; no mutation or idempotency ledger exists |
| Timeout/unavailable dependency | Injected readiness checks fail closed with 503; liveness remains independent. These are protocol tests, not PostgreSQL/Redis integration claims |
| Malformed dependency response | Truthy objects and other non-boolean results do not count as readiness success |
| Partial failure | Mixed successful/failed probes yield 503; a later healthy request recovers, proving stale results are not cached |
| Concurrent requests | IDs remain isolated before/after awaits; no shared mutable settings are changed |
| Cancellation | Middleware re-raises cancellation and clears context; timed-out probe cleanup executes. Cancelling a readiness request cleans up both in-flight probes. Liveness remains responsive while readiness waits |
| Stale state/concurrent update | No mutable business state or transaction is introduced. Immutable settings are fixed per app instance |
| Cross-seller reference | No seller lookup exists. The absent business paths still return 404. This is not tenant-authorization validation |
| Expired credentials/rate limit | Synthetic probe callbacks raise UNAUTHENTICATED/RATE_LIMITED application errors and readiness returns dependency 503, not caller 401/429. No authenticated provider adapter exists, so actual token expiry/refresh and provider retry contracts cannot yet be tested |
| External ambiguity/retry | No external mutation exists, so no ambiguous success or retry is invented. Stable errors alone cannot implement reconciliation |

## Findings resolved

### Exact money conversion depended on Decimal precision

**Problem:** a valid configured amount lost centimes under a reduced Decimal context. **File:** `src/marketing_ai/core/config.py`, `Settings.money_centimes()`. **Root cause:** multiplying a Decimal by the currency unit factor uses the caller's arithmetic precision before conversion to int. A regression test derived the approved delivery setting plus one centime, then reduced arithmetic precision; the original function returned 3500 instead of 3501 centimes.

**Smallest fix:** obtain the Decimal's exact integer ratio and perform the unit conversion using integer arithmetic. No business limit, validation rule, dependency or public interface changed. **Proof:** `test_money_conversion_is_independent_of_decimal_context` failed before the fix and now passes; existing exact-money/over-precision/float rejection tests and the full regression suite also pass.

### Additional behavioral evidence

New tests cover missing/invalid real factory startup, remaining configuration relationships, scalar mathematical bounds, all supported environments, repeated ID generation, uppercase UUID normalization, UUID-shaped invalid input, duplicate correlation headers, missing/null/list payloads, path/query validation, invalid response schemas, exception log secrecy, readiness recovery and cancellation. Non-finite/untrusted log extras, uncontrolled application errors and non-HTTP middleware passthrough are also checked. Test watchdogs and synthetic values are harness inputs, not new business constants.

### Prior implementation decisions retained

- Included routers are represented lazily by the locked FastAPI version. The old P01 test now verifies framework documentation paths and the public OpenAPI route inventory without relying on private storage classes.
- State-only dependencies are async, avoiding unnecessary worker-thread scheduling. Registered checks remain explicit async callables.
- Required settings are injected into the container at runtime; the previous environment-free app startup contract intentionally changes in P02. Package import remains environment-independent.
- Pydantic's mypy plugin handles the settings constructor; tests use explicitly dynamic dictionaries only at the raw configuration-input boundary. Production types remain narrow.
- Runtime logging tests capture the configured output sink directly, avoiding pytest's own raw log-record capture as a proxy for production output.

## Required-category applicability and senior review

| Review/category | Finding and evidence |
|---|---|
| Implementation correctness | Startup, canonical errors, both response headers and health semantics match the requirements. The money conversion defect was demonstrated before repair |
| Unit tests | Required settings, exact money, relationships, controlled errors, log formatting and context cleanup are exercised without external services |
| Integration/contract/API | Real ASGI route/handler/lifespan integration and actual Docker build/Uvicorn HTTP checks run. Probe doubles implement the real callback interface; no business rule is mocked |
| Architecture/dependency direction | Core error vocabulary has no framework dependency; presentation maps it to HTTP. The only production change in this follow-up is exact arithmetic in core configuration |
| Missing identifiers/malformed inputs | Unsafe/missing/duplicate request IDs, malformed/missing/schema-invalid bodies and path/query conversion errors are covered. Response schema failures produce safe 500 envelopes |
| State transitions | No business state machine exists, so transition rejection is not applicable. Immutable settings and probe failure-to-recovery behavior are tested instead |
| Budget/page/batch/text limits | Applicable configuration ordering and page boundaries are covered below/at/above named settings. No campaign-budget policy, batch endpoint or seller-instruction endpoint exists; enforcing their runtime limits here would invent future functionality |
| Authentication/permissions/tenants/admin | Public health/docs deliberately do not require identity. Controlled 401/403 mapping is tested, but no auth system or seller lookup exists to exercise ownership/capability checks. Business/admin/foreign-seller paths remain absent and return safe 404; this is not a claim of implemented authorization |
| Security and secrets | Secret repr/serialization, safe startup stderr, actual formatted request/error logs, malformed UUIDs and safe errors are checked. Container canaries prove exclusion and least-privilege runtime remains tested |
| Idempotency/concurrency/transactions | HTTP reads and probes have no logical persistent mutation to deduplicate. Repeated requests, concurrent contexts, concurrent probes and cancellation are tested. There is no DB state guard/transaction to mock or certify |
| Database integration | No repository, model, migration, query, index or constraint exists in P02. Starting a disposable PostgreSQL would test infrastructure availability rather than an implemented persistence contract; no DB integration PASS is invented |
| Redis/Celery integration | No Redis client or Celery task exists. Compose/parser and container isolation checks apply; queue delivery tests do not |
| LLM/Meta/internal-service contracts | No adapter or call exists, so no recorded provider schema or AI evaluation applies. Only the actual readiness extension point is exercised with synthetic outcomes |
| Failure/ambiguity | Connection failure, timeout, malformed probe responses, synthetic credential/rate failures and partial readiness are tested. No external mutation exists whose uncertain outcome requires reconciliation |
| Logging/metrics/observability | Controlled JSON/local formats, lifecycle events, request/correlation IDs and success/failure/duration records are covered. No external call or financial step requires new metrics here; existing later-phase telemetry obligations remain |
| Performance | Liveness completes while a readiness request is blocked; probes execute concurrently with explicit deadlines. No database query or list endpoint exists, so N+1/full-scan behavior is not applicable. This is deterministic behavioral evidence, not a production load benchmark |
| Documentation/migrations | README, this formal report and the 24-section learning document reflect the fix and expanded coverage. No persistence change requires a migration |
| Regression | All P00/P01/P02 default cases and explicit Docker tests pass. No security control, assertion or warning policy was relaxed. No numeric coverage percentage is claimed |

## Limits and handoff

Default readiness proves only that all **registered** checks succeeded. With no checks registered it does not certify database, Redis, Meta or LLM availability. Future probe adapters must supply their own centrally configured deadlines and use cancellation-cooperative I/O. P02 invents no health timeout constant.

Application-controlled HTTP failures before response headers are sent receive the envelope. A disconnect, ASGI-server parser rejection or error after a streaming response has begun cannot be rewritten by these handlers. P02 exposes no streaming endpoint. Request IDs are diagnostic metadata, not authentication or a full distributed tracing implementation.

Logging is deliberately restrictive: unknown messages become `external_log`, losing descriptive detail to avoid exposing arbitrary provider data. New operational events must be explicitly reviewed and allowlisted. No OpenTelemetry exporter, metrics backend, external call or financially sensitive workflow is introduced here. Readiness events already record success/failure and elapsed duration; future external adapters still require the designated metrics instrumentation.

No initialized Git index exists in this workspace, so no tracked-history secret audit is claimed. Tests cover intended build inputs, ignore rules and synthetic canaries. SecretStr redaction is not encryption or a secret store.

**P02 implementation, testing, validation and learning documentation pass for the stated scope. P03 may proceed.** No critical failure remains. Persistence, authentication, provider integrations and business-policy enforcement still require their designated implementations and gates.
