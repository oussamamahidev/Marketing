# P02 — Configuration, Logging, Request Context, Errors and Health

## 1. What We Built

P02 gives the FastAPI foundation a predictable runtime contract. The app validates its settings before serving, associates requests with safe identifiers, emits controlled operational logs, translates errors consistently and exposes separate liveness/readiness endpoints.

P01 supplied packaging, quality tools, a minimal factory and secure container basics. It had no required Python settings or application routes. P02 adds operational behavior without adding campaign management, authentication, persistence or AI.

```text
P01: installed package + factory + container
                    ↓
P02: validated settings + request context + safe errors/logs
                    ↓
Observable HTTP service with live/ready endpoints
                    ↓
Later persistence and business features consume these interfaces
```

The supplied TESTING P02 and VALIDATION P02 prompts pass: 234 default tests, 3 real container tests, Ruff and strict mypy. The formal review added 61 adversarial cases and repaired one proven exact-money conversion defect. See the [validation report](../architecture/p02-validation.md) for precise evidence, applicability and limits. P03 may proceed.

## 2. Objectives of This Phase

| Category | Requirement | Implementation | Why it matters |
|---|---|---|---|
| Functional | Operational health and consistent failures | Two health endpoints and four exception handlers | Clients and operators can interpret results consistently |
| Architecture | Keep boundaries explicit | Framework-independent error vocabulary, API translation, typed probe interface | Future business code need not construct HTTP responses |
| Security | Exclude unsafe inputs and secrets | SecretStr exclusions, safe startup diagnostics, UUID validation and log allowlist | Credentials and untrusted text do not become normal operational output |
| Reliability | Reject unusable settings and bound checks | Required settings, relationship validation, concurrent timed probes | The service cannot quietly assume missing business limits |
| Testing | Verify failure and concurrency paths | Config/API/log tests plus updated real-container checks | Success-only smoke tests would miss leakage, stale context and hanging probes |

The approved business values remain configuration assumptions. Parsing them does not enforce campaign policy or prove production readiness.

## 3. Files Created

| File | Purpose | Layer | Used By |
|---|---|---|---|
| `src/marketing_ai/core/__init__.py` | Shared runtime package | Core | Python imports |
| `src/marketing_ai/core/config.py` | Typed settings and safe loading | Core | Factory, later consumers |
| `src/marketing_ai/core/logging.py` | Safe formatters and request context | Core | Lifespan, middleware, readiness |
| `src/marketing_ai/core/errors.py` | Controlled application error vocabulary | Core | API handlers, readiness |
| `src/marketing_ai/api/__init__.py` | API package | Presentation | Python imports |
| `src/marketing_ai/api/dependencies.py` | Settings/probe dependencies and probe contract | Presentation | Routes, composition root |
| `src/marketing_ai/api/middleware.py` | HTTP identifiers and context lifetime | Presentation | FastAPI middleware stack |
| `src/marketing_ai/api/error_handlers.py` | Safe HTTP error translation | Presentation | FastAPI exception stack |
| `src/marketing_ai/api/v1/__init__.py` | Versioned router package | Presentation | Python imports |
| `src/marketing_ai/api/v1/router.py` | Assemble current operational routes | Presentation | Factory |
| `src/marketing_ai/api/v1/health.py` | Liveness/readiness behavior | Presentation | Router |
| `tests/unit/core/test_config.py` | Configuration contracts | Tests | Pytest |
| `tests/unit/core/test_logging.py` | Logging and cancellation behavior | Tests | Pytest |
| `tests/api/test_health.py` | Health and injected dependency failures | Tests | Pytest |
| `tests/api/test_error_format.py` | Errors, headers and concurrent context | Tests | Pytest |
| `docs/architecture/p02-validation.md` | Evidence and phase-gate limitations | Documentation | Reviewers |
| `docs/learning/P02-configuration-logging-errors.md` | Teach the actual implementation | Documentation | Developer |

### `src/marketing_ai/core/config.py`

**Purpose:** make configuration an explicit startup boundary. **Responsibility:** parse the environment/dotenv, validate values and relationships, conceal secrets and convert configured money exactly. **Must NOT do:** connect to databases, approve budgets or mutate resources. **Main components:** `Settings`, `ConfigurationError`, `load_settings()`, `money_centimes()`. **Dependencies:** Pydantic, Pydantic Settings and standard-library Decimal/types. **Used by:** `create_app()` and the settings dependency; covered by `test_config.py`.

### `src/marketing_ai/core/logging.py`

**Purpose:** emit useful operational events without arbitrary sensitive text. **Responsibility:** ContextVars, the `EVENTS` allowlist, `SafeFormatter` and process logging setup. **Must NOT do:** persist audit records or infer permissions from identifiers. **Main components:** request/correlation ContextVars, `SafeFormatter`, `configure_logging()`. **Dependencies:** standard-library logging, JSON and contextvars. **Used by:** lifespan, middleware and readiness; covered by logging and API tests.

### `src/marketing_ai/core/errors.py`

**Purpose:** name failures independently of HTTP. **Responsibility:** constrained codes and details. **Must NOT do:** attach raw provider messages, render responses or determine seller access. **Main components:** `ErrorCode`, `ErrorLocation`, `ErrorReason`, `ErrorDetail`, `ApplicationError`. **Dependencies:** standard library only. **Used by:** readiness and exception translation; tested through API behavior.

### `src/marketing_ai/api/dependencies.py`

**Purpose:** expose narrow runtime inputs to routes. **Responsibility:** retrieve app-scoped settings/probes and validate probe registration data. **Must NOT do:** construct a database client or invent a default deadline. **Main components:** frozen `ReadinessProbe`, async `get_settings()` and `get_readiness_probes()`. **Dependencies:** FastAPI request and core settings. **Used by:** factory and health routes.

### `src/marketing_ai/api/middleware.py`

**Purpose:** establish and clean up request context. **Responsibility:** safe UUID headers, response headers and completion/failure/cancellation events. **Must NOT do:** authenticate a caller or buffer response bodies. **Main components:** `safe_id()` and `RequestContextMiddleware`. **Dependencies:** Starlette ASGI/header types and core logging. **Used by:** the app's middleware stack; tested by API concurrency and cancellation cases.

### `src/marketing_ai/api/error_handlers.py`

**Purpose:** enforce the public error contract. **Responsibility:** map controlled errors to safe statuses/messages/details and retain request context. **Must NOT do:** expose exception text or perform retries. **Main components:** `ERRORS`, `error_response()`, the four handlers and `register_error_handlers()`. **Dependencies:** FastAPI/Starlette and core errors. **Used by:** FastAPI exception handling.

### `src/marketing_ai/api/v1/health.py` and `router.py`

**Purpose:** expose operational checks. **Responsibility:** liveness, concurrent bounded readiness and route assembly. **Must NOT do:** create business use cases or pretend that unregistered dependencies were checked. **Main components:** `HealthResponse`, `live()`, `ready()`, `run_probe()` and routers. **Dependencies:** FastAPI, asyncio, the probe contract and core errors/logging. **Used by:** `create_app()`; tested by `test_health.py` and real-container HTTP checks. The directory is versioned, but the required public URLs remain `/health/live` and `/health/ready`, without a `/v1` prefix.

## 4. Files Modified

| File | What Changed | Why |
|---|---|---|
| `src/marketing_ai/main.py` | Settings/probe injection, lifespan logging, middleware, handlers and router | Compose the runtime feature at one entrypoint |
| `pyproject.toml` | Explicit Pydantic/Settings dependencies and Pydantic mypy plugin | Support typed environment loading and correct strict constructor checking |
| `uv.lock` | Resolve added runtime requirements | Keep installation and container builds reproducible |
| `.env.example` | Environment/log settings, optional secret fields and approved business values | Provide the centralized initial runtime configuration |
| `docker-compose.yml` | Explicit app settings injection | Required settings reach the container while Postgres credentials remain separate |
| `README.md` | Current setup, health, headers, logging and verification instructions | Environment-free startup was a P01 contract and changes in P02 |
| `tests/conftest.py` | Settings from non-secret example, explicit injection and lifespan | Isolate tests from the developer's real secrets |
| `tests/unit/test_imports.py` | Current route inventory and canonical absent-route behavior | Preserve import safety while accepting intentional API changes |
| `tests/unit/test_foundation.py` | Compose fixtures include required app configuration | Continue testing real parsing, secret separation and setup preservation |
| `tests/integration/test_container.py` | Non-secret runtime env and live/ready assertions | Verify the actual default command under the new startup contract |

The ignored local `.env` also received only missing P02 entries and owner-only permissions. Its existing password was retained. This is local setup, not a distributable source artifact. No database models, authentication rules, Meta clients or AI graphs were created or modified.

During the subsequent P02 testing/validation step, the only production-code change was in `core/config.py`: `money_centimes()` now uses exact integer-ratio arithmetic. The four P02 test modules were expanded, and README, this learning document and the validation report were updated. That follow-up did not modify `.env`, business constants, dependencies or running infrastructure.

## 5. Architecture Explanation

The factory remains the composition root: it chooses configuration and wires the API. Core errors know nothing about FastAPI. The HTTP layer translates those errors; a later worker can interpret the same vocabulary without constructing a JSON response.

```text
Environment / .env
        │
        ▼
Settings ──► create_app() ──► lifespan ──► safe logging
                  │
HTTP ──► request-context middleware
                  │
                  ▼
           health router
             │        │
           live      ready ──► injected async ReadinessProbe checks
                       │
                       ▼ failure
                ApplicationError
                       │
                       ▼
               API error handler
                       │
                       ▼
            JSON envelope + response IDs
```

No business application/domain/infrastructure implementation exists in this slice. Operational routes do not need fabricated use-case or repository classes. The planned `Presentation → Application → Domain ← Infrastructure` direction is preserved: future domain rules will not depend on these HTTP handlers. Future adapters can implement the injected probe callable while routes depend only on its typed contract. There is no transaction, repository, gateway, worker or external write in this phase.

## 6. Request / Data Flow

At startup, `create_app()` uses explicitly injected settings or calls `load_settings()`. Invalid settings stop construction. Duplicate probe names are rejected. The factory stores immutable settings and the probe tuple on app state, then installs middleware, handlers and routes. Lifespan selects the logging format and emits start/stop events.

For an HTTP request:

1. Middleware accepts a single canonical UUID request/correlation header or supplies safe replacements.
2. It stores the IDs in request state and ContextVars, retaining reset tokens.
3. FastAPI matches a route. Liveness returns immediately. Readiness retrieves app probes through an async dependency and runs them concurrently.
4. A normal result becomes a typed response. An application, HTTP or request-validation failure goes through an exception handler.
5. The middleware adds both response headers and records status/duration.
6. Its `finally` block restores context, including on cancellation or failure.

Unexpected exceptions reach Starlette's outer server-error handler after user middleware unwinds. IDs therefore also live in request state; the 500 handler can produce matching headers/body even after ContextVars reset. The middleware already recorded the correlated failure. Cancellation propagates instead of inventing a successful response.

## 7. Theory You Need to Understand

### Typed configuration and fail-fast validation

**Definition:** turn external strings into constrained values before using them. **Why it exists:** deployments can omit variables, misspell values or combine individually valid but inconsistent settings. **How we use it here:** Pydantic Settings checks required values, types, bounds and relationships before serving. **What could go wrong without it:** a missing budget ceiling could become an implicit permissive default or fail halfway through a later request.

### Exact money representation

**Definition:** represent amounts with exact decimal inputs and integer minor units at storage boundaries. **Why it exists:** binary floating-point cannot represent many decimal fractions exactly. **How we use it here:** Decimal validates configured MAD amounts and `money_centimes()` converts them to integers; float inputs are rejected. **What could go wrong without it:** rounding inconsistencies at financial boundaries. Decimal in configuration does not authorize Decimal database storage; the project requires integer centimes there.

Exact representation does not imply every arithmetic operation stays exact. Decimal multiplication obeys the active precision context. The review reduced that context and proved the old conversion lost a centime. Integer-ratio conversion avoids that ambient rounding behavior; Python integer multiplication and division remain exact for already validated centime amounts.

### Structured logging and data minimization

**Definition:** emit events as named fields with a controlled schema. **Why it exists:** operators need searchable, comparable records, while arbitrary messages can contain secrets. **How we use it here:** JSON outside local, readable key/value fields locally, controlled event names and numeric status/duration. **What could go wrong without it:** query strings, Authorization headers, exception arguments or provider payloads could expose tokens. An allowlist sacrifices some diagnostic detail; new fields need deliberate review.

### Task-local context

**Definition:** ContextVars associate values with the current asynchronous execution context. **Why it exists:** many requests interleave on one thread, so a global variable or ordinary thread-local cannot distinguish them. **How we use it here:** each request sets IDs and resets the returned tokens in `finally`. **What could go wrong without it:** request B could inherit request A's identifier, making logs misleading. Background tasks copy context at creation; future long-lived tasks must establish their own lifecycle rather than assume these HTTP resets clear every copied context.

### ASGI middleware and exception boundaries

**Definition:** ASGI components exchange scope, receive and send messages asynchronously. **Why it exists:** a middleware can inspect metadata and wrap response headers without reading whole bodies. **How we use it here:** the middleware wraps `http.response.start`, passes non-HTTP scopes through and leaves body streaming alone. **What could go wrong without it:** middleware may consume a request body twice, lose identifiers on outer 500s or claim it can replace a response after headers were sent.

### Liveness versus readiness

**Definition:** liveness asks whether the service can respond; readiness asks whether its registered prerequisites currently succeed. **Why it exists:** restarting a healthy process during a database outage can worsen an incident. **How we use it here:** liveness ignores probes and readiness aggregates explicit checks. **What could go wrong without it:** a missing future integration could block all startup, or an empty readiness registry could be mistaken for a database availability guarantee.

### Cooperative cancellation and bounded concurrency

**Definition:** async deadlines cancel work, and async functions must yield control to respond. **Why it exists:** an unbounded dependency can tie up health requests. **How we use it here:** concurrent probe coroutines each receive an explicit timeout; cancellation is not swallowed as ordinary success. **What could go wrong without it:** serial checks add delays, swallowed cancellation leaks work, and a blocking synchronous call defeats an event-loop timeout. This mechanism cannot forcibly stop uncooperative code.

## 8. Practical Implementation Explanation

`Settings` consumes environment/dotenv strings and produces immutable typed fields. Environment values override dotenv; explicit constructor inputs support tests. Missing numeric business limits have no fallback. The non-secret `.env.example` is checked against BUSINESS_CONSTANTS, keeping approved defaults in the centralized configuration mechanism rather than route/domain literals.

Money is non-negative or positive according to the field, with exact centime precision. Percentages are mathematically bounded. Relationship validation checks budget ordering, stock floor versus advertising minimum, page size, backfill retention and the non-disableable approval requirement. Production/staging reject DEBUG. Invalid settings become `ConfigurationError` messages containing field names/error types, not supplied values.

The original `int(amount * 100)` conversion was insufficient: with arithmetic precision reduced to two digits, a validated amount of 35.01 MAD became 3500 centimes. The regression test derives its amount from the named delivery setting plus one centime, without copying a business default. The corrected method uses:

```python
numerator, denominator = amount.as_integer_ratio()
return numerator * 100 // denominator
```

The factor is a currency-unit conversion, not a business threshold. Validation already disallows fractional centimes, so the integer division does not discard a valid fractional minor unit. `test_money_conversion_is_independent_of_decimal_context` was run before the fix and failed, then passed afterward. This is a behavioral regression test rather than an assertion about the implementation's chosen syntax.

`SafeFormatter` never calls `record.getMessage()` or formats exception data. It selects a known event name or `external_log`, reads current IDs and permits only finite numeric status/duration extras. Configuring logging routes Uvicorn errors through that formatter and disables raw access lines. This protects the configured handlers; future custom handlers must follow the same contract.

`safe_id()` rejects multiple header values and anything outside canonical UUID syntax. UUID length is a protocol rule, not a new business threshold. A safe incoming correlation ID is preserved independently from the request ID; absent/unsafe correlation falls back to the current request ID. These are tracing fields, not proof of caller identity.

`ApplicationError` accepts only controlled enum codes/details. `error_response()` maps it to a fixed status/message and serializes safe details. Validation errors retain only a broad location such as `body` and a controlled reason, dropping input values and field paths. Unexpected failures receive a generic 500. HTTP statuses without an explicit supported mapping fall back to internal error; future protocols should add deliberate mappings rather than pass through arbitrary messages.

`ReadinessProbe` supplies a name, an async callable and an explicit positive finite timeout. `run_probe()` measures duration and accepts only a strict boolean true. `ready()` uses `asyncio.gather()` and returns 503 if any result fails. With no registered checks, all checks succeed vacuously, producing ready. No database URL is contacted just because it exists in settings.

## 9. Important Classes, Functions, Interfaces, and Schemas

| Name | Type | File | Responsibility |
|---|---|---|---|
| `Settings` | Pydantic Settings class | `core/config.py` | Typed immutable runtime inputs |
| `load_settings` | Function | `core/config.py` | Safe startup error translation |
| `money_centimes` | Method | `core/config.py` | Exact named MAD conversion |
| `SafeFormatter` | Logging formatter | `core/logging.py` | Controlled JSON/local output |
| `configure_logging` | Function | `core/logging.py` | Install the process output policy |
| `ApplicationError` | Exception | `core/errors.py` | Framework-independent failure value |
| `ErrorCode` | Enum | `core/errors.py` | Stable machine-readable vocabulary |
| `ErrorDetail` | Frozen dataclass | `core/errors.py` | Controlled location/reason pair |
| `RequestContextMiddleware` | ASGI middleware | `api/middleware.py` | Identifier validation, headers and cleanup |
| `ReadinessProbe` | Frozen dataclass/interface | `api/dependencies.py` | Typed asynchronous check and deadline |
| `get_settings` | Async dependency | `api/dependencies.py` | App-scoped validated settings |
| `get_readiness_probes` | Async dependency | `api/dependencies.py` | Registered checks without thread work |
| `HealthResponse` | Pydantic schema | `api/v1/health.py` | Alive/ready response vocabulary |
| `run_probe` | Async function | `api/v1/health.py` | Execute and classify a bounded check |
| `error_response` | Function | `api/error_handlers.py` | Canonical JSON response and ID headers |
| `create_app` | Factory | `main.py` | Wire settings, lifespan and HTTP components |

The most important boundary is between `ApplicationError` and `error_response()`: one describes a controlled failure, the other decides how HTTP presents it. The probe contract likewise separates health orchestration from future dependency-specific connection code.

## 10. Database Changes

No database changes were introduced in this phase.

There are no tables, migrations, sessions, SQL queries or transaction boundaries. The existing local PostgreSQL volume and Redis service were preserved. Readiness test callbacks do not pretend to be repository integration tests.

## 11. API Changes

| Endpoint | Purpose | Request | Success | Failure | Auth/use case |
|---|---|---|---|---|---|
| `GET /health/live` | Process liveness | No body or business inputs | 200, `{"status":"alive"}` | Framework failures use canonical envelope | Public operational route; no business use case |
| `GET /health/ready` | Registered prerequisites | No body or business inputs | 200, `{"status":"ready"}` | 503, `DEPENDENCY_UNAVAILABLE` | Public operational route; no business use case |

The existing framework docs remain available. `/` and `/health` remain absent but now return the canonical 404 envelope. Unsupported methods produce canonical 405 with an allowed-method header when safe.

Every application HTTP response includes request/correlation headers. Errors have this shape:

```json
{
  "error": {
    "code": "RESOURCE_NOT_FOUND",
    "message": "Resource not found",
    "details": []
  },
  "request_id": "<same UUID as X-Request-ID>"
}
```

No campaign, seller, approval or authentication endpoint was added. HTTP error codes such as 401/403 exist as translation vocabulary, not proof that authentication has been implemented.

## 12. Security Considerations

Secret fields use `SecretStr`, `repr=False` and `exclude=True`. This conceals normal representation/serialization; it does not encrypt memory or replace a secret manager. Startup translation strips invalid input data. Safe logging excludes arbitrary messages, tracebacks, headers, customer text and query strings rather than trying to identify every possible secret pattern.

UUID validation prevents untrusted identifier text from reaching headers/log fields. Duplicate headers are not trusted. Concurrent ContextVar tests reduce the risk of mixing one request's metadata with another's. IDs remain attacker-supplied diagnostic data when valid and must never become authorization or idempotency evidence.

Approval cannot be disabled through configuration. Actual policy enforcement still belongs to later domain/application phases. There is no seller data access to authorize or tenant lookup to test here. Existing absent-route tests continue to reject synthetic foreign-seller paths without echoing their input.

The container receives non-secret business settings at runtime. Compose does not forward the Postgres password to the app. Real build-context tests retain root/nested environment-file and key canaries. Non-root, read-only execution and immutable application files remain verified.

## 13. Error Handling

| Failure | Expected Behavior | Why |
|---|---|---|
| Missing mandatory setting | Stop startup with field/type diagnostic | No silent business fallback |
| Inconsistent settings | Configuration error before serving | Individual field validity is insufficient |
| Invalid payload | 422 `VALIDATION_FAILED`, safe location/reason | Do not echo untrusted values |
| Authentication/permission exception vocabulary | 401 `UNAUTHENTICATED` / 403 `FORBIDDEN` | Distinguish caller authentication from denied action |
| Unknown route | 404 `RESOURCE_NOT_FOUND` | Stable client contract |
| Unsupported method | 405 `METHOD_NOT_ALLOWED`, safe Allow header | Retain useful HTTP semantics |
| State conflict vocabulary | 409 `STATE_CONFLICT` | Differentiate state conflicts from malformed input |
| Rate limit vocabulary | 429 `RATE_LIMITED` | Distinguish throttling; limiter itself is not implemented |
| Provider failure vocabulary | 502/503/504 controlled codes | Distinguish invalid response, unavailability and timeout |
| Failed/malformed/timed-out readiness check | Generic dependency 503 | Do not expose dependency internals |
| Unexpected exception | 500 `INTERNAL_ERROR` with request ID | Prevent traces/raw exception text reaching clients |
| Cancellation | Propagate and reset context | Do not fabricate a success or swallow shutdown |

```text
Controlled failure or framework exception
                   ↓
Registered API handler
                   ↓
Fixed status/message + controlled details
                   ↓
Canonical response with matching request ID
```

After response headers have been sent, HTTP cannot replace the status/body with a new envelope. Transport disconnects and server-level parsing errors also sit outside this application contract. No streaming endpoint is introduced here.

## 14. Testing Strategy

### Unit Tests

`test_config.py` derives test inputs from the non-secret example and checks their agreement with BUSINESS_CONSTANTS. Every required setting is removed in turn to prove failure. Tests cover dotenv precedence, hidden secrets, rejected approval disablement, frozen settings, production logging restrictions and exact centimes. Missing-value tests clear relevant environment variables and use a temporary working directory, preventing the developer's `.env` from masking errors.

The formal review extends this with stock/backfill/seller-budget relationships, supported environments, scalar mathematical bounds, currency rejection and actual factory subprocesses. Missing/invalid ENVIRONMENT values must terminate construction without echoing an input canary. The Decimal-context regression proves exact conversion independently of caller arithmetic precision.

`test_logging.py` passes synthetic secrets through log messages, arguments, exceptions and extras; output must omit them. It checks JSON/local format selection, context fields and middleware cleanup on cancellation.

It also rejects non-finite and non-numeric status/duration extras, checks that application errors reject uncontrolled codes/details, and verifies non-HTTP scopes pass through without creating an HTTP request context.

### Integration Tests

The existing Docker suite builds actual images. It verifies runtime ownership, excluded development packages/secrets, read-only execution, import and the default Uvicorn HTTP command. P02 supplies required values from a filtered non-secret template and checks both health URLs. A separate context-copy build proves excluded secrets never enter the build context. No real user `.env` or database volume is used.

### API Tests

`test_health.py` exercises the app through ASGI with lifespan enabled. `test_error_format.py` checks supported HTTP statuses, application failures, unhandled exceptions, malformed bodies, unsupported methods and unknown routes. Error-only routes exist inside tests, not production.

Additional API tests cover missing/null/list payloads, invalid path/query identifiers and invalid response schemas. Response validation failures must produce a generic 500 with both supplied IDs preserved. Success cases prove uppercase UUID normalization and fresh IDs on later header-free requests. A failed request followed by a successful one must leave neither its secret nor its context behind.

### Security Tests

Secret canaries must not appear in configuration repr/dumps, errors or the configured runtime log sink. Empty, oversized, unsafe and duplicated IDs are replaced. An actual request containing a synthetic Authorization/query secret still logs its ID without the secret. This observes runtime output, not pytest's separate raw record capture.

### Failure Tests

Injected readiness callbacks return false, return a truthy malformed object, raise an exception or wait until cancelled. Readiness must return 503, suppress the canary exception message and preserve liveness. Probe timeout tests check cleanup, not only the status.

Synthetic rate-limit and unauthenticated dependency errors also become readiness 503; the caller of a public health endpoint is not blamed for the dependency's credentials. A mixed-success probe set first fails and then recovers, demonstrating that readiness does not cache stale results. These are callback contract tests, not claims of actual provider refresh/retry behavior.

### Boundary Tests

Budget ordering, default page size, stock floor and backfill use values immediately below, at and above their named configured boundaries. Money tests reject empty/placeholder/non-finite/negative and over-precision values plus binary floats. Percentage mathematical endpoints, positive versus non-negative scalar settings, and invalid probe deadlines are covered. These verify configuration contracts; campaign policy, batch-size and seller-instruction request boundaries remain future work because those endpoints/policies do not exist yet.

### Concurrency / Idempotency Tests

Concurrent requests read their IDs before and after yielding; each response must retain its own context and the caller context must be clear afterward. Two readiness checks wait for each other's entry, proving concurrent execution. There is no persistent mutation or idempotency state to test in P02.

An event-controlled readiness request remains blocked while liveness completes, proving the two behaviors are independent without relying on a fragile elapsed-time performance assertion. Cancelling a readiness request runs cleanup for both in-flight callbacks. Test watchdog deadlines only keep the suite bounded; they do not establish application business limits or production latency SLOs.

## 15. Commands Used

```bash
uv sync --locked
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked mypy src tests
uv run --locked pytest -q
uv run --locked pytest -q -m container
uv run --locked uvicorn marketing_ai.main:create_app --factory --host 127.0.0.1 --port 8000
```

Locked sync verifies dependency metadata. Ruff checks style/imports, mypy checks types, the default tests need no daemon, and the explicit container selection needs Docker daemon access. Default tests still use the Compose CLI for isolated parsing. During implementation the restricted environment used a writable temporary uv cache and authorized Docker access; these are execution accommodations, not product settings.

Container/setup commands remain in the [README](../../README.md). `uv lock` was used intentionally after adding dependencies; normal verification uses the existing lock. No Alembic or database migration command applies yet.

## 16. How to Test It Manually

1. Run `uv sync --locked`, then `test -e .env || cp .env.example .env`. For an existing P01 file, add missing template settings without overwriting its password. PostgreSQL is not needed for these HTTP checks.
2. Start the factory using the Uvicorn command above.
3. In another terminal, run:

```bash
curl -i http://127.0.0.1:8000/health/live
curl -i http://127.0.0.1:8000/health/ready
curl -i http://127.0.0.1:8000/unknown
curl -i -X POST http://127.0.0.1:8000/health/live
curl -i -H 'X-Correlation-ID: 123e4567-e89b-12d3-a456-426614174000' http://127.0.0.1:8000/health/live
curl -i -H 'X-Request-ID: unsafe id' http://127.0.0.1:8000/health/live
```

Expect two successful health responses, canonical 404/405 envelopes, both ID headers, preservation of the valid correlation UUID and replacement of the unsafe request ID. Local logs contain event/context fields. There is no business state to inspect afterward.

Stop the server, then try an isolated process override:

```bash
ENVIRONMENT=invalid uv run --locked python -c 'from marketing_ai.main import create_app; create_app()'
```

It should fail with a safe ENVIRONMENT diagnostic without editing `.env`. To observe JSON output, run the server with `ENVIRONMENT=test`. Use the automated injected-probe tests to observe dependency failure without inventing a production debug endpoint.

## 17. Design Decisions

### Required runtime values rather than fallback business defaults

**Decision:** store initial values in the central configuration template and require them at construction. **Why:** the binding project rules require missing constants to fail loudly. **Alternatives:** dataclass defaults or parsing Markdown at runtime. **Why not selected:** fallback values hide deployment mistakes; Markdown is policy documentation, not a production parser contract. Tests connect the template to the approved specification.

### Allowlisted logs rather than unrestricted formatted messages

**Decision:** retain reviewed events and controlled fields. **Why:** unknown provider text can contain credentials or personal data. **Alternatives:** regex redaction of arbitrary messages or a new logging framework. **Why not selected:** regex cannot enumerate every secret format; a new package is unnecessary for the current narrow schema. The tradeoff is reduced descriptive detail for unknown events.

### Pure ASGI middleware with request-state backup

**Decision:** wrap send directly and store context in both ContextVars and request state. **Why:** this avoids body buffering and preserves IDs when outer error handling runs after context reset. **Alternatives:** endpoint-only IDs or a process global. **Why not selected:** endpoint code misses routing errors; globals are unsafe with concurrent requests.

### Explicit empty readiness registry

**Decision:** no fabricated PostgreSQL/Redis checks. **Why:** their adapters do not exist and the prompt explicitly forbids reporting them unhealthy prematurely. **Alternatives:** try connections directly in health routes. **Why not selected:** it would couple presentation to infrastructure and invent connection/timeout behavior. The tradeoff is that current readiness only covers the empty registry.

### Async dependencies for app-state access

**Decision:** the settings/probe dependencies are async. **Why:** reading app state is immediate and needs no worker-thread scheduling. **Alternatives:** synchronous dependencies. **Why not selected:** FastAPI dispatches them through worker machinery that adds no useful isolation for this work.

## 18. What I Should Learn From This Phase

- [ ] Explain why required configuration is checked before serving.
- [ ] Distinguish default business assumptions from measured production data.
- [ ] Convert exact configured MAD amounts to integer centimes.
- [ ] Explain why SecretStr is redaction, not encryption.
- [ ] Trace request IDs through middleware, ContextVars and outer error handling.
- [ ] Explain why controlled logging can be safer than arbitrary text redaction.
- [ ] Distinguish liveness from the registered readiness contract.
- [ ] Explain how async timeouts depend on cooperative cancellation.
- [ ] Distinguish an error vocabulary from implemented authorization or idempotency.
- [ ] Run both default and actual container checks and interpret their limits.

## 19. Interview Questions From This Phase

**Q: Why validate settings before the first HTTP request?**

**Answer:** deployment errors become visible before the service can perform work with missing or inconsistent limits.

**Q: Does SecretStr encrypt a password?**

**Answer:** no. It masks common representations; this implementation also excludes fields from repr/dumps. Secret storage and encryption are separate concerns.

**Q: Why are request IDs stored in ContextVars?**

**Answer:** async requests share threads and interleave. ContextVars keep execution-context values separate across tasks.

**Q: Why also store IDs on request state?**

**Answer:** the outer 500 handler can run after middleware has reset task context; request state preserves the response's ID.

**Q: Can a valid incoming UUID authorize a seller action?**

**Answer:** no. It is untrusted diagnostic metadata even when syntactically valid.

**Q: What does ready mean with no probes?**

**Answer:** all registered checks succeeded because none are registered; it does not assert database or provider availability.

**Q: Why reject a truthy dictionary from a readiness callback?**

**Answer:** a malformed provider result should not accidentally count as success. The contract requires an actual boolean true.

**Q: Why can an async timeout fail to bound blocking code?**

**Answer:** cancellation is cooperative; a function that blocks the event loop prevents the deadline callback from running promptly.

**Q: What information is lost with allowlisted logging?**

**Answer:** arbitrary library messages and traces become generic events. This avoids accidental disclosure but requires deliberate safe instrumentation for deeper diagnostics.

**Q: Why test containers when ASGI tests pass?**

**Answer:** ASGI tests do not prove packaging, non-root permissions, build-context exclusion or the default Uvicorn command works in the runtime image.

**Q: Can Decimal arithmetic lose centimes even without a float?**

**Answer:** yes. Multiplication can round according to the active Decimal precision. Converting an already validated amount through its exact integer ratio avoids that dependency on ambient arithmetic context.

## 20. Common Mistakes

Hard-coding a budget in a route bypasses centralized configuration. Consume named settings and let later policies own financial decisions.

Logging `str(exc)` or a full request object can expose credentials or user text. Emit a reviewed event and controlled fields instead.

Using a global request ID mixes concurrent requests. Use ContextVars and reset tokens in `finally`, including cancellation paths.

Returning ready for any truthy provider object hides malformed results. Require strict boolean success and fail closed otherwise.

Calling blocking dependency code inside an async readiness function defeats its timeout. Use cancellation-cooperative adapters with explicit deadlines.

Overwriting an existing `.env` can invalidate an initialized database password. Add missing settings and preserve current secrets.

Treating 401/403 enum values as completed authentication confuses representation with enforcement. No sensitive endpoint should rely on the enum alone.

## 21. Debugging Guide

**Problem:** startup reports a missing setting. **Possible cause:** an old P01 `.env` or a launch from another directory. **How to diagnose:** inspect the non-secret field names in `ConfigurationError` and compare local keys with `.env.example`. **How to fix:** add the missing approved settings in the configuration mechanism; do not insert a fallback in domain code.

**Problem:** a money conversion differs when called from another computation. **Possible cause:** arithmetic context affects a Decimal operation. **How to diagnose:** reproduce with `localcontext()` and reduced precision, as in the regression test. **How to fix:** use the centralized exact conversion; do not duplicate Decimal multiplication or float arithmetic at call sites. This phase's proven instance was fixed in `money_centimes()`.

**Problem:** a relationship error appears despite valid numbers. **Possible cause:** inconsistent budget ordering, stock/page/backfill constraints, disabled approval or non-local DEBUG. **How to diagnose:** review the relationships in `validate_policy_relationships()` without dumping secret fields. **How to fix:** correct the named configuration inputs.

**Problem:** readiness says ready while Postgres is down. **Possible cause:** no PostgreSQL probe is registered in P02. **How to diagnose:** inspect factory registration, not a URL's mere presence. **How to fix:** consume the probe extension point when the database phase supplies the adapter and deadline; this phase intentionally has no such check.

**Problem:** a caller's ID changes. **Possible cause:** invalid UUID syntax or duplicate headers. **How to diagnose:** check the request headers and returned IDs. **How to fix:** supply one canonical UUID per ID header; do not loosen validation for arbitrary text.

**Problem:** an exception has no descriptive log message. **Possible cause:** the formatter intentionally drops arbitrary messages and traces. **How to diagnose:** correlate the stable event, status and request ID. **How to fix:** add reviewed safe event metadata when needed, never enable raw payload logging.

**Problem:** Docker tests fail before building. **Possible cause:** daemon access or missing cached/network artifacts. **How to diagnose:** read the actual Docker failure. **How to fix:** provide the authorized daemon/build environment and rerun the explicit selection; do not silently skip it.

**Problem:** a pytest log assertion sees raw data or an empty capture. **Possible cause:** pytest captures raw log records separately, and fixture-time streams differ from the runtime sink. **How to diagnose:** distinguish LogRecord capture from formatted stderr output. **How to fix:** exercise the configured formatter/output sink as the production behavior under test.

## 22. Connection to Previous Phases

P00 supplies the binding architecture, money model, approved constants and non-disableable approval invariant. P02 turns those constant names into validated configuration while retaining P00's documentation checks.

P01 supplies the installed package, factory, lockfile, strict tools, Docker isolation and tests. P02 extends those interfaces instead of replacing them. P01's prior validation report is historical: its environment-free startup and empty API schema deliberately become required settings and two operational routes here.

## 23. Preparation for the Next Phase

Later persistence code can obtain validated settings, register an asynchronous readiness check with its own centrally configured deadline and translate safe application failures at the HTTP boundary. Logging/context/error facilities are available without adding database dependencies to domain code.

This phase guarantees successful construction has validated its required settings; it does not guarantee a database connection, deployed schema, authenticated principal or financial policy result. Those later features must add their own requirements, adapters and tests. No next-phase implementation is included.

## 24. Final Phase Summary

### In one sentence

P02 adds validated configuration and safe, correlated HTTP operations to the existing FastAPI foundation.

### Before this phase

The repository could install and run a minimal app with framework documentation and no required runtime business settings.

### After this phase

The app requires validated configuration, exposes live/ready endpoints, emits controlled logs and returns canonical errors with request identifiers. The supplied testing and validation gates pass, the precision defect is fixed, and the learning documentation reflects the verified implementation.

### Most important engineering lesson

Operational contracts should make invalid state visible early while exposing only the information needed to diagnose it safely.
