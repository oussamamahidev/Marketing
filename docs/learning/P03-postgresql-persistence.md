# P03 — PostgreSQL Persistence Foundation

## 1. What We Built

P03 adds SQLAlchemy async engines and sessions, application-owned transactions, Alembic migration tooling, a real PostgreSQL readiness check and database operation metrics. It adds no business tables. The only initial persistent schema artifact is Alembic's revision tracking table.

P02 provided configuration, logs, request context, canonical errors and injectable readiness callbacks. P03 connects those operational interfaces to PostgreSQL and establishes how later repositories obtain sessions without committing behind the application's back.

```text
P02: typed settings + operational HTTP contracts
                     ↓
P03: engine + fresh sessions + transaction context + Alembic
                     ↓
Verified persistence primitives and database readiness
                     ↓
Later application use cases and infrastructure repositories
```

The supplied TESTING P03 and VALIDATION P03 prompts pass: 254 default tests, 17 real PostgreSQL tests and 3 container tests, plus Ruff and strict mypy. Testing found and fixed two defensive boundaries: Alembic now retains its fixed safe diagnostic, and a session dependency outside lifespan fails closed. The five deployment pool/timeout values remain protected-environment inputs with no invented defaults; tests do not silently choose them. P04 may proceed.

## 2. Objectives of This Phase

| Category | Requirement and implementation | Why it matters |
|---|---|---|
| Functional | Async engine, fresh sessions and explicit transaction context | Later use cases can persist atomic changes |
| Architecture | Infrastructure owns ORM mechanics; application owns transaction boundary | Repository operations cannot silently commit partial business work |
| Security | Secret URL validation, safe errors/logs, parameterized SQL and documented separate roles | Connection credentials and untrusted values stay out of output and SQL syntax |
| Reliability | Bounded pools, connect/wait/readiness deadlines, rollback and cleanup | Unavailable PostgreSQL cannot be mistaken for readiness |
| Schema evolution | Single Alembic lineage, metadata integration and empty-database smoke command | Schema changes become explicit and testable |
| Testing | Real disposable PostgreSQL instead of transaction mocks | Constraints, visibility and rollback are database behavior |

Required configuration exists as typed fields without defaults. BUSINESS_CONSTANTS section 11 records that initial deployment values are unresolved; startup rejects missing settings. The already approved business values remain unchanged.

## 3. Files Created

| File | Purpose | Layer | Used By |
|---|---|---|---|
| `alembic.ini` | Credential-free migration configuration | Tooling | Alembic CLI and smoke tool |
| `migrations/env.py` | Async migration connection and metadata integration | Infrastructure/tooling | Alembic |
| `migrations/script.py.mako` | Revision generation template | Tooling | Developers generating revisions |
| `migrations/versions/0001_persistence_foundation.py` | No-op initial migration lineage | Schema history | Alembic |
| `src/marketing_ai/infrastructure/__init__.py` | Adapter package | Infrastructure | Imports |
| `src/marketing_ai/infrastructure/database/__init__.py` | Database adapter package | Infrastructure | Imports |
| `src/marketing_ai/infrastructure/database/base.py` | Shared declarative base and naming conventions | Infrastructure | Alembic and future models |
| `src/marketing_ai/infrastructure/database/session.py` | Engine, session scopes, readiness and disposal | Infrastructure | Lifespan, API dependency and future workers |
| `src/marketing_ai/infrastructure/database/transaction.py` | Explicit commit/rollback scope | Infrastructure | Future application use cases |
| `src/marketing_ai/infrastructure/database/metrics.py` | Fixed-label outcome/latency metrics | Infrastructure | Database operations |
| `src/marketing_ai/infrastructure/database/migrations.py` | One-head/empty-database migration smoke tool | Infrastructure/tooling | CLI and integration tests |
| `tests/integration/database/conftest.py` | Disposable PostgreSQL and isolated databases | Tests | Database integration suite |
| `tests/integration/database/test_session.py` | Real lifecycle/transaction/pool/API tests | Tests | Pytest database selection |
| `tests/integration/database/test_migrations.py` | Real migration, drift and branching tests | Tests | Pytest database selection |
| `tests/unit/test_database.py` | Configuration, metadata and missing-lifespan checks | Tests | Default suite |
| `docs/architecture/p03-validation.md` | Implementation evidence and remaining gates | Documentation | Reviewers |
| `docs/learning/P03-postgresql-persistence.md` | Explain this phase's implementation | Documentation | Developer |

### `base.py`

**Purpose:** one metadata registry for future ORM models. **Responsibility:** declare `Base` and deterministic names for primary/foreign/unique/check/index objects. **Must NOT do:** create tables on startup or contain domain behavior. **Main component:** SQLAlchemy `DeclarativeBase` with `MetaData`. **Dependencies:** SQLAlchemy only. **Used by:** migration environment; verified by empty metadata and migration tests.

### `session.py`

**Purpose:** manage async persistence resources. **Responsibility:** construct a bounded engine, create fresh session scopes, check readiness and dispose the pool. **Must NOT do:** share a global session, create schemas, commit a use case or retry writes. **Main component:** `Database`. **Dependencies:** validated settings, SQLAlchemy, asyncio and metrics. **Used by:** lifespan, `get_session()` and worker-style test scopes.

### `transaction.py`

**Purpose:** expose explicit transaction ownership. **Responsibility:** wrap `session.begin()`, reject implicit nesting, record outcomes and propagate failures. **Must NOT do:** choose business rules or claim an uncertain commit definitely rolled back. **Main component:** `transaction()`. **Dependencies:** SQLAlchemy session plus safe logging/metrics. **Used by:** application-style test use cases; actual business use cases come later.

### `metrics.py`

**Purpose:** measure new DB operations. **Responsibility:** counters/histograms for readiness and transaction outcomes/latency. **Must NOT do:** include URLs, SQL, seller IDs or request IDs as labels. **Main components:** `CHECKS`, `CHECK_DURATION`, `TRANSACTIONS`, `TRANSACTION_DURATION`. **Dependencies:** Prometheus client. **Used by:** session and transaction helpers. It registers metrics but adds no public endpoint.

### Migration files

**Purpose:** make schema changes repeatable. **Responsibility:** `env.py` loads validated configuration, uses `Base.metadata` and executes Alembic through an async connection; the Mako file templates future revisions; the initial revision establishes one head without business DDL. **Must NOT do:** run automatically during app startup or embed credentials in INI. **Dependencies:** Alembic and SQLAlchemy, plus settings/logging in the environment. **Used by:** migration CLI and integration tests.

### `infrastructure/database/migrations.py`

**Purpose:** verify a clean schema bootstrap. **Responsibility:** require one head, refuse existing public tables/views, upgrade and inspect the recorded revision. **Must NOT do:** delete existing databases or serve as a production restore procedure. **Main components:** `single_head()`, `check_database()`, `smoke()` and `main()`. **Dependencies:** Alembic, SQLAlchemy and `Database`. **Used by:** module CLI and actual PostgreSQL tests.

## 4. Files Modified

| File | What Changed | Why |
|---|---|---|
| `core/config.py` | Required secret PostgreSQL URL and bounded pool/timeout fields | Reject missing or unsupported persistence configuration |
| `core/logging.py` | Three controlled transaction event names | Record transaction lifecycle without raw exception text |
| `main.py` | Lifespan engine creation/disposal and mandatory PostgreSQL probe | Tie resource lifetime to serving process |
| `api/dependencies.py` | Fresh session dependency; readiness fails if lifespan is absent | Avoid session sharing and false readiness |
| `api/v1/health.py` | Updated ownership description | Actual PostgreSQL registration is composed outside the route |
| `pyproject.toml`, `uv.lock` | Database/migration/metrics dependencies and explicit DB test marker; mypy source/package mapping | Reproducible runtime, real integration selection and nested test typing |
| `.env.example` | Required URL, Compose URL and unresolved operational settings | Make missing configuration explicit without inventing values |
| `BUSINESS_CONSTANTS.md` | P03 operational settings and pending ownership decision | Keep numeric configuration ownership centralized |
| `docker-compose.yml` | Inject approved settings and container-specific DB URL | Separate host addressing from Compose networking |
| `Dockerfile`, `.dockerignore` | Include credential-free Alembic files in runtime | Permit a separate migration command from the deployment image |
| `tests/conftest.py` | Isolated DB test values | Keep default tests independent of local deployment secrets |
| `tests/unit/core/test_config.py` | URL canary conforms to new PostgreSQL URL grammar | Continue testing secrecy under the P03 contract |
| `tests/api/test_health.py` | Explicit empty registry only inside the generic callback test | Production default readiness now requires PostgreSQL |
| `tests/unit/test_foundation.py` | Synthetic Compose DB config, require URL while excluding unrelated credentials | Preserve real parser/security assertions |
| `tests/integration/test_container.py` | Include migrations and require unavailable-DB readiness 503 | Test the new runtime image and intentional health change |
| `README.md` | Setup, transactions, roles, migrations, tests and pending values | Current operator/developer instructions |

No real `.env` or existing database volume was modified during this implementation. Existing P00/P01/P02 historical reports remain unchanged.

The P03 testing/validation follow-up changed `migrations/env.py`, `api/dependencies.py`, database test modules, this document, the validation report and README. It removed runtime logging configuration from the migration environment because it suppressed Alembic's own fixed safe failure text. Alembic still catches raw connection errors and emits only `Migration failed; check database access and revision consistency` to its CLI. The update did not change schemas, dependencies, business constants, credentials or running infrastructure.

## 5. Architecture Explanation

```text
Validated settings
        │
        ▼
FastAPI lifespan ──► Database ──► async engine / bounded pool
        │                │
        │                └──► fresh AsyncSession per scope
        │                              │
        ▼                              ▼
health readiness             application-owned transaction()
        │                              │
        ▼                              ▼
     SELECT 1                 future repository operations
        │                              │
        └──────────── PostgreSQL ───────┘

Alembic CLI ──► async migration environment ──► Base.metadata
                        │
                        └──► revision history + alembic_version
```

Presentation obtains sessions through a dependency and coordinates health probes. Infrastructure owns SQLAlchemy and schema tools. The application will select transaction boundaries; domain policies remain independent of ORM/session details. No repository interface or concrete business repository is fabricated here.

The intended direction remains `Presentation → Application → Domain ← Infrastructure`. P03 provides the infrastructure primitives for that design, not a complete application/domain implementation. PostgreSQL is authoritative; no Redis persistence or cross-service transaction is introduced.

## 6. Request / Data Flow

At construction, settings validate before the app can serve. Lifespan configures logs, constructs a lazy engine, stores `Database` on app state and registers the PostgreSQL readiness callback. Engine construction does not connect. Shutdown disposes the engine and removes it from app state.

For a future route using `get_session()`:

1. The dependency enters `database.session()` and receives a new `AsyncSession`.
2. The application enters `transaction(session)` before its first query.
3. Repository operations execute parameterized SQL using that session.
4. Success exits the transaction and commits; an exception/cancellation triggers rollback mechanics.
5. Dependency exit closes the session and releases its connection.

The pattern is exercised by test-only routes and use cases; production has no such business endpoint yet. Workers use a process/event-loop-owned `Database` and a fresh scope per task, rather than reusing an HTTP session.

Readiness separately acquires a connection, executes a fixed `SELECT 1`, records outcome/latency and releases it under the configured deadline. Failure becomes false, which the existing API probe runner translates into canonical 503. Liveness never executes this query.

## 7. Theory You Need to Understand

### Engine, pool and session

**Definition:** an engine manages database connectivity; its pool reuses connections; a session tracks a unit of ORM work and its transaction. **Why it exists:** creating a network connection for every operation is expensive, while sharing mutable session state across tasks is unsafe. **How we use it here:** one engine per lifespan and a sessionmaker that constructs a fresh session per scope. **What could go wrong without it:** concurrent requests interfere with transaction state, or unbounded connections overload PostgreSQL. See the [SQLAlchemy async session guidance](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html#using-asyncsession-with-concurrent-tasks).

### Explicit transaction ownership

**Definition:** a transaction groups operations into one commit or rollback boundary. **Why it exists:** a use case may depend on several writes succeeding together. **How we use it here:** the application chooses `transaction(session)`; repositories must not commit. **What could go wrong without it:** one repository persists half a use case before another operation fails. Flush sends SQL but is not the same as commit.

### Async cancellation and resource cleanup

**Definition:** cancellation interrupts an awaiting task; context managers must release resources during unwinding. **Why it exists:** disconnected requests and shutdowns cannot leave connections indefinitely checked out. **How we use it here:** nested async session/transaction scopes and an explicit cancellation regression test. **What could go wrong without it:** pool starvation and abandoned transactions. Cooperative cancellation is not a guarantee against every process crash or network failure.

### Migration lineage and metadata

**Definition:** revisions describe schema evolution; metadata describes the models currently expected by code. **Why it exists:** deployed databases evolve independently of new application processes. **How we use it here:** one initial revision, shared metadata and Alembic's async connection bridge. **What could go wrong without it:** multiple unmerged heads, missing deployment steps or create-all calls that hide migration drift. The [Alembic async cookbook](https://alembic.sqlalchemy.org/en/latest/cookbook.html#using-asyncio-with-alembic) explains its connection bridge.

### Backpressure through bounded pools

**Definition:** finite resource capacity forces excess work to wait or fail. **Why it exists:** database connection capacity is limited across all service processes. **How we use it here:** pool size, overflow and acquisition timeout are required typed settings. **What could go wrong without it:** a traffic spike consumes the database's connection budget and prevents recovery/admin access. Pool capacity is per process, not global across a deployment.

### Least privilege and parameterization

**Definition:** a role receives only needed permissions; query parameters represent values independently from SQL syntax. **Why it exists:** compromised application code should not automatically gain schema/admin authority, and untrusted values must not become SQL. **How we use it here:** documented runtime/migration role separation and actual parameterized insert tests. **What could go wrong without it:** an application can alter schema or a crafted string changes the statement. SQL identifiers need identifier quoting, not value placeholders.

### Ambiguous commit outcomes

**Definition:** a lost connection can prevent a client from learning whether a commit completed. **Why it exists:** a server response may be lost after durable work succeeds. **How we use it here:** failures propagate without automatic retry; a generic transaction failure event does not claim rollback certainty. **What could go wrong without it:** blindly retrying later financial work can duplicate effects. Idempotency and reconciliation remain later business requirements.

## 8. Practical Implementation Explanation

`Database` receives validated settings and constructs `create_async_engine()` with explicit pool capacity, overflow and wait timeout. `pool_pre_ping=True` checks reused connections. Echo is disabled and bind parameters are hidden in engine diagnostics. The driver receives a configured connection timeout. No session object is stored globally.

`async_sessionmaker(..., expire_on_commit=False, autoflush=False)` constructs sessions on demand. Disabling expiration avoids surprise attribute-triggered I/O after commits in future async code; disabling autoflush makes repository flush points explicit. Neither setting permits sharing a session or avoids SQL constraints.

```python
async with database.session() as session:
    async with transaction(session):
        # Application coordinates future repository operations here.
        ...
```

`transaction()` checks for an already active transaction before beginning. This includes SQLAlchemy's automatic transaction start after a query: the application should enter its transaction first. It records committed, failure or cancelled outcomes without serializing SQL or exception messages. It does not retry, create savepoints automatically or decide business conflict semantics.

`check_ready()` covers pool acquisition, connection and query with `asyncio.timeout()`. It emits fixed-label metrics in `finally`; cancellation propagates. The outer readiness runner logs the controlled result and determines the HTTP response. If lifespan has not installed a database, readiness fails closed.

Alembic reads the secret URL from settings directly instead of interpolating it through ConfigParser. This avoids percent-encoded-password interpolation problems. Online migrations use a non-pooling async engine and `connection.run_sync()` for Alembic's migration operations. Offline mode renders PostgreSQL SQL without connecting. Raw migration failures become a fixed safe diagnostic.

Alembic's CLI owns presentation of that fixed diagnostic. The migration environment must not install the application runtime logging formatter: that formatter correctly converts unreviewed logs to `external_log`, but doing so made an operator lose the controlled message needed to distinguish a failed migration command. The failure test uses an unavailable connection URL containing a password canary and checks both message and non-disclosure.

The smoke command checks exactly one revision head before connecting, verifies no existing public tables/views, runs upgrade and reads the resulting revision. It never drops objects. Its empty-schema guard is a smoke-test precondition, not a concurrency lock or production backup policy.

## 9. Important Classes, Functions, Interfaces, and Schemas

| Name | Type | File | Responsibility |
|---|---|---|---|
| `Base` | Declarative base | `database/base.py` | Shared metadata and constraint names |
| `Database` | Resource manager | `database/session.py` | Engine, session factory, readiness and close |
| `Database.session` | Async context manager | `database/session.py` | Fresh session and cleanup, no automatic commit |
| `Database.check_ready` | Async callback | `database/session.py` | Bounded PostgreSQL query and metrics |
| `transaction` | Async context manager | `database/transaction.py` | Application-controlled transaction mechanics |
| `get_session` | Async dependency | `api/dependencies.py` | Request scope session acquisition |
| `single_head` | Function | `database/migrations.py` | Require exactly one revision head |
| `smoke` | Function | `database/migrations.py` | Empty database to verified migration head |
| `MigrationCheckError` | Controlled exception | `database/migrations.py` | Safe smoke-tool errors |

`Base` contains no mapped product entity. The session and transaction helpers are infrastructure APIs that future application code will compose; they are not authorization or tenant-isolation policies.

## 10. Database Changes

The initial no-op revision is `0001_persistence_foundation`. Alembic creates its standard `alembic_version` table with the revision identifier and primary-key bookkeeping. The revision's upgrade/downgrade functions add no business DDL. There are no seller/campaign/Meta/AI tables, business columns, relationships or indexes.

Integration tests create a separate test-only `transaction_probe` table with an integer primary key and text value. That table belongs to test metadata, not `Base.metadata` or migrations, and disappears when the disposable database is removed.

Existing local databases were not migrated or altered. Future schema changes must register models in migration metadata and introduce explicit reviewed revisions.

## 11. API Changes

`GET /health/live` remains public and returns 200 with `{"status":"alive"}` without accessing PostgreSQL. `GET /health/ready` remains public but now requires the automatically registered PostgreSQL check: successful connectivity yields 200/ready; unavailable, rejected or exhausted connections yield canonical 503 `DEPENDENCY_UNAVAILABLE`. Missing application lifespan also yields 503.

Both endpoints keep request/correlation headers. They accept no business request body and invoke no business use case. No new public route or metrics endpoint was added. Request-scoped sessions are available to future routes; only tests use the dependency in an endpoint so far.

## 12. Security Considerations

Database URLs stay SecretStr fields excluded from repr and model dumps. They are not stored in Alembic INI, Docker build arguments or committed credentials. The P02 formatter drops arbitrary messages, query text and exception traces; P03 adds only controlled transaction events. Engine echo is disabled.

The runtime role should receive CONNECT, schema USAGE and only needed table/sequence privileges. It should not own the schema/database or have SUPERUSER, CREATEDB or CREATEROLE. Migrations use a distinct owner with DDL authority. This separation is documented, not provisioned against an existing deployment. Local bootstrap/test ownership is explicitly not the production role model.

SQLAlchemy parameterization is tested with a malicious-looking value that is stored unchanged as data. Disposable database names/role setup use psycopg's identifier/literal composition, not raw interpolation of untrusted identifiers. Generated test credentials live in a temporary owner-only file and are removed with the container.

No tenant-owned resource exists, so a passing foundation test does not certify tenant authorization. Remote production connections should use verified TLS and deployment-managed secrets. Metrics use only controlled outcome labels.

## 13. Error Handling

| Failure | Expected Behavior | Why |
|---|---|---|
| Missing URL/pool/timeouts | Startup configuration error | No silent deployment assumptions |
| Unsupported/malformed URL | Safe validation failure | Restrict the supported async PostgreSQL driver |
| Pool exhausted | Acquisition timeout; readiness fails within deadline | Bound waiting and fail closed |
| Rejected credentials/refused TCP | Readiness 503, liveness 200 | Dependency failure is not process death |
| Use-case exception | Rollback through transaction context and propagate | Caller decides business presentation |
| Unique constraint violation | Database rejects and transaction rolls back | Atomicity includes earlier statements |
| Cancellation | Unwind scopes and release connection | Avoid abandoned work/pool starvation |
| Already active transaction | Reject helper entry | Prevent hidden nested ownership/commits |
| Failed commit | Propagate failure with no automatic retry | Outcome may be uncertain |
| No/multiple migration heads | Reject before smoke upgrade | Avoid ambiguous schema lineage |
| Nonempty smoke target | Refuse without deleting objects | Protect existing state from inappropriate smoke use |
| Migration driver failure | Fixed credential-free diagnostic | Do not print connection secrets |

Raw database exceptions remain infrastructure failures until a future application translates them into domain/application errors. Current unexpected HTTP errors still receive P02's safe canonical 500. Readiness deliberately translates its failures to dependency 503.

## 14. Testing Strategy

### Unit Tests

New tests reject unsupported/malformed database URLs, absent credentials, zero pool size/timeouts and unlimited negative overflow. Existing required-setting tests automatically include the new fields. Metadata remains empty and the migration directory has one head. Missing lifespan must not claim readiness.

### Integration Tests

The database selection starts real PostgreSQL in a disposable container on a random loopback port. It creates a non-superuser test role and a unique owned database per test. Real queries prove commit, rollback, uniqueness behavior, no implicit commit, nested-ownership rejection, cancellation, session separation, pool exhaustion/recovery and readiness metrics. The role owns only its disposable test database, which is different from the production restricted runtime contract.

Migration tests upgrade an empty database, repeat head, check metadata agreement, downgrade and re-upgrade. They inspect actual tables/version state, exercise a percent-encoded password through the CLI and reject a synthetic second head before any schema change. No real `.env` is read; migration tests run from a temporary working directory with isolated settings.

The container selection still verifies non-root ownership, read-only execution, excluded secrets/development files and real default Uvicorn startup. It now expects ready=503 with no PostgreSQL while live remains 200. Migration artifacts are included in the image.

### API and Security Tests

Test-only routes exercise `get_session()` concurrently through actual ASGI dependency cleanup. Real PostgreSQL readiness checks test healthy, refused-port and rejected-password cases; responses must not echo the credential canary. Parameterized inserts prove hostile-looking text stays data. Prior error/ID/log-secret tests remain present.

The testing follow-up adds a route requesting a session before lifespan. It must receive canonical 503 `DEPENDENCY_UNAVAILABLE`, just as readiness does, instead of an attribute-error 500. This prevents an accidental lifecycle-order failure from being treated as an internal application crash.

### Failure and Boundary Tests

Tests hold exactly configured pool-plus-overflow connections, attempt one more acquisition and observe timeout, then release and recover. Cancellation after an insert must leave no committed row. A duplicate primary key proves a partial transaction is rolled back. Synthetic harness values are centralized in test fixtures and are not production defaults or new business policy.

### Concurrency / Idempotency Tests

Two tasks and two HTTP requests receive different session objects while executing concurrently. Repeated migration upgrade at head is a no-op. There is no campaign or financial mutation idempotency contract yet; session isolation alone does not implement one.

## 15. Commands Used

```bash
uv sync --locked
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked mypy src tests
uv run --locked mypy src tests migrations
uv run --locked pytest -q
uv run --locked pytest -q -m database
uv run --locked pytest -q -m container
```

Database/container selections require authorized Docker access and cached or downloadable images. They are explicitly deselected from the default fast suite, never silently skipped. The lock was intentionally updated for SQLAlchemy, psycopg, Alembic and Prometheus client. No SQLite substitute is used for PostgreSQL semantics.

After required deployment settings are finalized:

```bash
uv run --locked alembic heads
uv run --locked alembic upgrade head
uv run --locked alembic current
uv run --locked alembic check
```

The smoke module command is for a separate empty disposable database. Ordinary migrations run explicitly under migration credentials; app startup never runs them.

## 16. How to Test It Manually

1. Resolve the five database settings in BUSINESS_CONSTANTS section 11 and add them to the ignored local environment. They currently have no approved defaults.
2. Set a URL-encoded host `DATABASE_URL` and a container-host `COMPOSE_DATABASE_URL` as appropriate, preserving existing credentials. Do not print or commit them.
3. Start PostgreSQL using the existing Compose setup after configuration is complete. Use a separately provisioned migration-role URL for Alembic, and run the migration commands above.
4. Start the app with `uv run --locked uvicorn marketing_ai.main:create_app --factory --host 127.0.0.1 --port 8000`.
5. Request `/health/live` and `/health/ready`; both should return 200 with valid settings/connectivity.
6. In a separate test environment, provide a syntactically valid URL to an unavailable port. Startup can still construct the lazy engine; liveness remains 200 and readiness returns a safe 503.
7. Run the real integration suite for rollback/concurrency verification. Do not create demonstration tables or drop objects in the developer's existing database.

The scripted tests perform these database behaviors in their own disposable environment even while deployment defaults are pending.

## 17. Design Decisions

### Async SQLAlchemy with psycopg

**Decision:** SQLAlchemy 2.x async engine with the psycopg driver. **Why:** it supports the required ORM/pool API and PostgreSQL async connection flow. **Alternatives:** raw driver operations everywhere or a synchronous application engine. **Why not selected:** raw calls would duplicate lifecycle/ORM work; synchronous request I/O would require extra thread orchestration.

### No global AsyncSession

**Decision:** process/event-loop-owned engine and fresh session scopes. **Why:** engines pool connections while sessions contain mutable transaction state. **Alternative:** one shared session or implicit task-local scoped session. **Why not selected:** explicit scopes are easier to reason about and test under concurrency/cancellation.

### No-op baseline revision

**Decision:** establish the migration lineage without business tables. **Why:** P03 forbids campaign/Meta/AI schema work but requires a real head upgrade. **Alternatives:** invent a generic business table or postpone all migration execution. **Why not selected:** one expands product scope; the other leaves schema tooling untested.

### Explicit configuration instead of guessed limits

**Decision:** required typed pool/timeout fields remain unset until the owner's decision. **Why:** the binding context prohibits invented thresholds. **Alternative:** adopt test values as deployment defaults. **Why not selected:** test harness settings do not establish PostgreSQL capacity or approved operating policy.

### Separate migration execution

**Decision:** ship migration artifacts but never run upgrades in lifespan. **Why:** deployment DDL needs explicit ownership and privileges. **Alternative:** every app worker auto-upgrades. **Why not selected:** concurrent starts can race DDL, require overprivileged runtime users and hide deployment failures.

## 18. What I Should Learn From This Phase

- [ ] Distinguish engine, pool, connection, session and transaction.
- [ ] Explain why every concurrent task needs its own session.
- [ ] Explain why repositories must not silently commit.
- [ ] Demonstrate rollback after failure, constraint violation and cancellation.
- [ ] Explain how pool limits multiply across processes.
- [ ] Explain why liveness can pass while readiness fails.
- [ ] Trace Alembic metadata, revisions, heads and version tracking.
- [ ] Distinguish test-only tables and credentials from production schema/configuration.
- [ ] Explain runtime-role versus migration-owner privileges.
- [ ] Explain why failed commits must not be blindly retried.

## 19. Interview Questions From This Phase

**Q: Why can an engine be reused but a session cannot be shared concurrently?**

**Answer:** the engine coordinates pooled connections; the session maintains mutable unit-of-work and transaction state for one logical scope.

**Q: Does session close commit work?**

**Answer:** no. This implementation rolls back uncommitted work on scope exit; the application transaction context owns commit.

**Q: Why does the helper reject an already active transaction?**

**Answer:** transaction ownership must be explicit. A query can have started an implicit transaction, and silently nesting or committing it would hide the actual boundary.

**Q: Why use real PostgreSQL for these tests?**

**Answer:** mock success/failure cannot prove database constraints, visibility, pooling or rollback mechanics.

**Q: What does the initial migration create?**

**Answer:** no business DDL; Alembic maintains its version table and records the single baseline revision.

**Q: Why can percent signs in a database URL be troublesome for Alembic configuration?**

**Answer:** ConfigParser uses percent-based interpolation. Passing the validated URL directly to the engine avoids that intermediate parser.

**Q: Does a transaction failure prove no write happened?**

**Answer:** not in every case. A connection failure during commit can hide a successful commit, so later mutations need idempotency/reconciliation.

**Q: Why are readiness timeouts separate from pool/connect timeouts?**

**Answer:** readiness needs one overall bound covering acquisition, connection and the query; underlying mechanisms have their own waits.

**Q: Why not give the runtime user database ownership?**

**Answer:** ownership grants DDL authority beyond ordinary application reads/writes. Migration and runtime responsibilities should be separated.

**Q: Does a passing integration suite approve the pending deployment limits?**

**Answer:** no. Synthetic values exercise behavior; the owner's operational decision and production capacity review remain separate.

## 20. Common Mistakes

Sharing a session across requests can mix transaction state; create a fresh scope per request/task. Calling commit inside a repository can persist half a use case; let the application transaction context commit. Starting a query before the explicit transaction can trigger automatic transaction creation; enter the use-case scope first.

Using `create_all()` at application startup hides schema history; use explicit Alembic revisions. Copying synthetic test pool values into production bypasses configuration ownership; finalize values centrally. Logging an engine URL or driver exception can expose secrets; preserve the controlled logging/error boundary.

Treating any connection error as permission to retry a write can duplicate committed work; leave uncertainty explicit. Running the smoke tool against a populated database is inappropriate; it requires a fresh disposable target and refuses existing tables/views.

## 21. Debugging Guide

**Problem:** app or Compose refuses startup for missing database settings. **Possible cause:** P03 values are intentionally unresolved or an older local file lacks keys. **How to diagnose:** read the named field diagnostic and template. **How to fix:** finalize values centrally and add them without overwriting credentials; no fallback should be inserted into code.

**Problem:** liveness passes but readiness returns 503. **Possible cause:** wrong host, rejected credentials, unavailable PostgreSQL or exhausted pool. **How to diagnose:** correlate request ID and controlled readiness events, inspect database/service availability without dumping the URL. **How to fix:** correct connection/role configuration or release leaked work; do not remove the required PostgreSQL check.

**Problem:** migrations fail with unclear driver details. **Possible cause:** access or revision inconsistency; raw driver text is intentionally suppressed. **How to diagnose:** verify approved settings, connectivity with protected tooling, revision heads and server-side operational logs. **How to fix:** correct the underlying deployment issue without logging passwords.

**Problem:** Alembic reports only `external_log` after migration failure. **Possible cause:** application runtime logging was installed inside `migrations/env.py`. **How to diagnose:** run the failed command against a protected invalid test URL and confirm the static migration diagnostic is missing. **How to fix:** leave runtime logging configuration out of the migration environment; Alembic can present the caught fixed error while raw driver details remain suppressed.

**Problem:** a test sees connection closure during PostgreSQL startup. **Possible cause:** the Docker image temporarily serves a Unix socket during initialization. **How to diagnose:** distinguish Unix-socket readiness from the final TCP listener. **How to fix:** the fixture now waits with `pg_isready -h 127.0.0.1` before creating test roles/databases.

**Problem:** mypy reports duplicate conftest modules. **Possible cause:** multiple test directories without package files. **How to diagnose:** inspect module path mapping. **How to fix:** configured explicit package bases and the src mypy path preserve strict analysis; no module is excluded.

**Problem:** the transaction helper rejects a session. **Possible cause:** an earlier query or outer context already started a transaction. **How to diagnose:** inspect the use-case boundary and `session.in_transaction()`. **How to fix:** make the outer application scope own the complete transaction rather than silently committing or nesting.

## 22. Connection to Previous Phases

P00 defines PostgreSQL authority, money storage, transaction ownership and safety invariants. P01 supplies packaging, Docker and tooling. P02 supplies typed settings, safe logging, correlation and canonical errors. P03 extends these through composition and changes readiness intentionally from an empty registry to required PostgreSQL availability.

Prior configuration/HTTP/container tests are retained and adapted only where the P03 contract changes. Prior historical reports remain valid for their original checkpoint; they do not describe current environment-free database behavior.

## 23. Preparation for the Next Phase

Future application work can receive a fresh session, own a transaction, use shared metadata and add explicit schema revisions. It must still define domain policies, seller-scoped queries, identity/permission checks, idempotency and any required locking. The infrastructure does not supply these automatically.

Deployment values must be finalized before a real app instance can start, using the centralized protected environment configuration. The supplied P03 testing/validation gates pass. No next-phase feature has been implemented.

## 24. Final Phase Summary

### In one sentence

P03 implements and validates the PostgreSQL resource, transaction, migration and readiness foundation while leaving deployment operating values explicitly unset until configured.

### Before this phase

The app had typed business configuration and generic operational health but no persistence resources or schema tooling.

### After this phase

Real PostgreSQL tests verify migrations, atomic rollback, isolated concurrent sessions, bounded pooling, fail-closed readiness and safe migration diagnostics; protected deployment configuration remains required before launch.

### Most important engineering lesson

Resource lifetimes, transaction ownership and configuration decisions must be explicit; successful test fixtures do not authorize production assumptions.
