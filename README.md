# Maroc Affiliate AI Marketing Assistant

P01 establishes packaging and tooling; P02 adds configuration, safe logging, request IDs, errors and health endpoints. P03 adds async PostgreSQL sessions, explicit transactions and Alembic. There are no business tables, Meta adapters or AI workflows. Import makes no connections; lifespan creates a lazy database engine, and readiness now checks PostgreSQL. Redis is not yet contacted.

This README owns developer setup and verification commands. Architecture and business policy remain in [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md), [BUSINESS_CONSTANTS.md](BUSINESS_CONSTANTS.md), the [architecture overview](docs/architecture/overview.md), [domain glossary](docs/architecture/domain-glossary.md), [non-functional requirements](docs/architecture/non-functional-requirements.md), and [profitability model](docs/architecture/profitability.md). The [P00 validation report](docs/architecture/p00-validation.md) records the prerequisite approval.

## Local setup

Install Python 3.14 and uv in the version range required by `pyproject.toml`. Run from this directory:

```bash
uv sync --locked
uv run --locked python -c 'import marketing_ai'
test -e .env || cp .env.example .env
```

`uv.lock` pins runtime and development dependency resolution. Keep it committed with `pyproject.toml`. `uv sync --locked` fails if metadata and lock disagree; dependency changes require an intentional `uv lock` followed by all quality checks. Python uses the `src/marketing_ai` layout and an installed package; tests do not inject `src` into PYTHONPATH.

App construction now requires `ENVIRONMENT` and every configurable business value in `.env.example`. The template contains the owner-approved MVP defaults from BUSINESS_CONSTANTS. Existing P01 installations must add the new entries to their existing `.env`, preserving their password. Values must be revisited using real operating data before production launch. Environment variables override `.env`; missing or invalid required values stop startup with a non-secret configuration error. Package import alone still needs no settings or services.

`core/config.py` owns typed validation. Settings are immutable; money converts exactly to integer centimes. `DATABASE_URL` is now required and must use `postgresql+psycopg://` with a host, database and credentials. It remains excluded from repr/serialization. `REDIS_URL` and `POSTGRES_PASSWORD` remain optional secret fields in the app. `ENVIRONMENT` supports `local`, `test`, `staging` and `production`; staging/production reject DEBUG logging.

**P03 configuration decision pending:** the five database pool/timeout settings in [BUSINESS_CONSTANTS section 11](BUSINESS_CONSTANTS.md#11-database-operational-configuration-p03) have no approved deployment values yet. They are intentionally blank in `.env.example` and required at startup. Add approved values to your existing `.env` before running the app or Compose; do not copy test harness values as deployment policy. Existing local credentials and the PostgreSQL volume have not been changed.

Set `DATABASE_URL` for tools running on the host (normally loopback) and `COMPOSE_DATABASE_URL` for the app container (normally hostname `postgres`). URL-encode special characters in credentials. Compose injects the latter as the app's `DATABASE_URL`. Keep both in the ignored `.env` or a deployment secret store, never build arguments or committed files. This phase does not run migrations automatically against your existing database.

## Quality checks

```bash
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked mypy src tests
uv run --locked pytest -q
uv run --locked pytest -q -m container
uv run --locked pytest -q -m database
```

To apply formatting, run `uv run --locked ruff format .`. The default suite covers P00 documents, package imports, minimal HTTP behavior and configuration. It requires Git, uv and the Docker Compose CLI for isolated configuration parsing, but no Docker daemon, live database, Redis, account credentials or LLM access. The separate `-m container` suite builds real images and requires Docker daemon access and either cached dependencies/base images or registry access. Run all three selections for the phase gate; container tests are explicitly deselected from the fast default suite, never silently skipped. Temporary test containers/images are cleaned up, and your running Compose services are not touched. The environment must first be synchronized from the lockfile. Async tests use the supported `httpx2` ASGI transport described in [Starlette's testing guidance](https://starlette.dev/testclient/), with explicit application lifespan and the asyncio backend. Warnings remain errors.

## Run the app

```bash
uv run --locked uvicorn marketing_ai.main:create_app --factory --host 127.0.0.1 --port 8000 --reload
```

Open `http://127.0.0.1:8000/docs` or `/openapi.json`. The schema exposes only two operational endpoints:

| Request | Behavior |
|---|---|
| `GET /health/live` | 200 with `{"status":"alive"}`; never checks dependencies |
| `GET /health/ready` | 200 with `{"status":"ready"}` when every registered probe succeeds; canonical 503 otherwise |

P03 always registers a PostgreSQL check during lifespan. Readiness runs `SELECT 1` within its configured short deadline and returns canonical 503 for unavailability, rejected credentials or exhausted connections. It also fails closed if lifespan has not run. Liveness remains independent and healthy during a database outage. Other registered probes run concurrently; Redis has no check until its integration phase.

Every HTTP response carries `X-Request-ID` and `X-Correlation-ID`. Incoming IDs must be single canonical UUID values; invalid or duplicated values are replaced. These IDs are for tracing, never identity or authorization. `/` and `/health` return canonical 404 responses:

```json
{"error":{"code":"RESOURCE_NOT_FOUND","message":"Resource not found","details":[]},"request_id":"<UUID matching X-Request-ID>"}
```

The same envelope handles validation, application, HTTP and unexpected errors, without raw inputs or exception messages. Local logs use readable key/value fields; other environments use JSON. Logs include safe event names, request context, status and elapsed time. Arbitrary messages, headers, payloads and tracebacks are omitted; unknown library messages become `external_log`. Raw Uvicorn access logs are disabled because they can include sensitive query strings.

## Local infrastructure and container

Docker supports two local workflows. The password-configured base setup uses your ignored `.env` and can start only dependencies with:

```bash
docker compose up -d --wait postgres redis
```

For a fully Docker-managed development stack with no local PostgreSQL password or app settings, use the local-only overlay:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml --profile app up -d --build --wait
docker compose -f docker-compose.yml -f docker-compose.dev.yml --profile app logs app
```

The overlay uses PostgreSQL `trust` authentication, a fresh `postgres_dev_data` volume, approved MVP development configuration, and a deliberately non-secret identity key. It is only for one local developer machine; never use it for shared, staging, or production environments. Services still bind to loopback.


Build and check the app image independently of `.env` or the database:

```bash
docker build -t marketing-ai:p03 .
docker run --rm --entrypoint id marketing-ai:p03
docker run --rm --entrypoint python marketing-ai:p03 -c 'import marketing_ai'
```

The runtime user is non-root, application files are root-owned, and only the installed runtime environment is copied into the final stage. `.dockerignore` allowlists package/build inputs; the Dockerfile never copies `.env`, tests, credentials or the entire working directory. Locked installation uses uv's [documented Docker workflow](https://docs.astral.sh/uv/guides/integration/docker/) and a custom Python image as described by [FastAPI](https://fastapi.tiangolo.com/deployment/docker/). Python and uv build images are pinned by digest; update their digests deliberately when applying base-image fixes. Local PostgreSQL/Redis tags stay on their selected major/minor versions and may receive upstream patch rebuilds.

To run the optional application service with Compose:

For the password-configured app profile, fill the required database and identity settings in `.env`, then run:

```bash
docker compose --profile app up -d --build --wait
docker compose --profile app logs app
```

Both Compose modes use a read-only app filesystem, temporary `/tmp`, dropped capabilities, and no privilege escalation. The app never receives `POSTGRES_PASSWORD` or `REDIS_URL`.

`down` preserves PostgreSQL's volume. Compose explicitly passes the app's environment, logging level, business/database settings and database connection URL; the separate `POSTGRES_PASSWORD` and Redis URL are not forwarded. The application profile uses a read-only filesystem, temporary `/tmp`, dropped capabilities and no privilege escalation. Do not treat the local Redis/network configuration as a production deployment contract; P22 owns that contract.

## PostgreSQL sessions and migrations

The engine pool is bounded by configured pool size plus overflow **per process**. A request gets a fresh `AsyncSession` through `get_session`; a worker creates its own `Database` per process/event loop and uses `database.session()` per task. Never share a session between concurrent tasks. Session exit closes it and rolls back uncommitted work; it never commits implicitly.

Application use cases explicitly own `async with transaction(session)` before their first query. Success commits, exceptions/cancellation roll back; repositories execute/flush but must not commit. The helper rejects an already active transaction. A connection failure during commit can leave an uncertain outcome: no automatic retry is implemented, and future mutating use cases must reconcile it.

After filling the required settings, use a migration-role database URL supplied through your secret environment:

```bash
uv run --locked alembic heads
uv run --locked alembic upgrade head
uv run --locked alembic current
uv run --locked alembic check
```

The initial revision has no business DDL; Alembic creates only `alembic_version`. Metadata is `Base.metadata`; future model registrations and schema changes need explicit revisions. The image includes `alembic.ini` and `migrations`, but app startup does not execute migrations. New revisions are authored in the checkout, not a read-only runtime container.

For a **fresh disposable database**, the smoke command rejects multiple/no heads and existing tables/views, upgrades to head and verifies the recorded revision:

```bash
uv run --locked python -m marketing_ai.infrastructure.database.migrations
```

The `-m database` suite provisions its own disposable PostgreSQL container, generated credentials, a non-superuser test role and a separate database per test; it never uses your real `.env` or Compose volume. It verifies migrations, metadata agreement, commit/rollback, cancellation, concurrent sessions, pool exhaustion, readiness failures and metrics. Docker access is required; failures are not silently skipped.

Production must separate the migration owner (schema/DDL authority) from the runtime role (CONNECT, schema USAGE, and only required table/sequence permissions). The runtime role must be NOSUPERUSER, NOCREATEDB and NOCREATEROLE; it must not own the database/schema or receive blanket DDL grants. Grant table privileges/default privileges from the migration owner when tables are introduced. The P01 local bootstrap role and disposable test owner are development conveniences, not the production privilege model. Use verified TLS for remote PostgreSQL and secret injection for both roles.

Database check and transaction counters/histograms record fixed outcome labels, success/failure and latency in the Prometheus registry. No URL, SQL, seller ID or request ID is a metric label; no public metrics endpoint is introduced here.

## Phase boundary

No seller/resource lookup, Meta/LLM call or financial mutation exists yet. Authentication, tenant isolation, mutation policy, retries and provider reconciliation remain later-phase requirements. Database availability and transaction primitives do not implement those business controls.

## P01 implementation verification

Historical P01 checkpoint, verified on 2026-09-20 before the P02 API/configuration changes:

| Check | Result |
|---|---|
| Locked install and `import marketing_ai` | PASS; package also imports outside the repository without PYTHONPATH injection |
| Ruff lint and formatting | PASS |
| Strict mypy over source and tests | PASS |
| Entire pytest suite | PASS: 69 default tests plus 3 real container tests; both selections run, no skipped tests |
| Docker build | PASS with the locked runtime dependencies and pinned base-image digests |
| Container runtime | PASS: non-root UID, read-only filesystem, dropped capabilities, no external networking, and successful default Uvicorn startup |
| Container HTTP smoke check | PASS: documentation responds and OpenAPI has no business paths |
| Runtime image contents | PASS: package imports; no `.env`, pytest, Ruff or mypy installed in the app environment |
| Compose configuration | PASS with a placeholder password; missing password is rejected. local PostgreSQL/Redis were subsequently started for setup; tests preserve those services |
| Secret handling | Ignore rules verified in a disposable Git repository; distributable inputs reviewed for credential patterns. This workspace has no initialized Git index, so no tracked-file audit is claimed |

The existing P00 test module received only the formatting required by Ruff; its AST was verified unchanged. No architecture/business constants, domain features, Meta integration, AI workflows or database business models were changed. Temporary smoke-test containers were stopped and removed.

The local Docker installation used its legacy builder successfully and emitted a buildx deprecation notice; this was an environment notice, not a failed image build. Install the Docker Buildx plugin for the modern build path.

The supplied P01 testing and validation prompts now pass. See the [P01 validation report](docs/architecture/p01-validation.md) for evidence and applicability, and the [P01 learning document](docs/learning/P01-project-foundation.md) for the implementation explanation. P02 may proceed.

## P02 implementation verification

Historical checkpoint before P03's intentional database configuration/readiness changes:

Verified on 2026-09-20: 234 default tests and all 3 real container tests pass. Strict mypy passes for 22 source/test files; Ruff lint and formatting pass. The formal P02 review added 61 adversarial cases and fixed centime conversion to remain exact under a caller's Decimal precision. Configuration tests cover every required setting, real startup failures, relationships, precision, immutability and secret exclusion. API tests cover health, dependency failures/timeouts/recovery/cancellation, canonical errors, unsafe headers and concurrent request context. Container checks exercise the default Uvicorn command with the required non-secret settings.

The supplied TESTING P02 and VALIDATION P02 prompts pass. See the [P02 validation report](docs/architecture/p02-validation.md) for evidence and applicability, and the [P02 learning document](docs/learning/P02-configuration-logging-errors.md) for the implementation and testing explanation. P03 may proceed.

## P03 implementation verification

The supplied TESTING P03 and VALIDATION P03 prompts pass: 254 default tests, 17 real PostgreSQL tests and 3 container tests; Ruff and strict mypy pass. Testing fixed safe Alembic failure presentation and fail-closed session acquisition outside lifespan. See the [P03 validation report](docs/architecture/p03-validation.md) and [P03 learning document](docs/learning/P03-postgresql-persistence.md). Configure the five database limit/timeout values through protected environment configuration before a real app startup. P04 may proceed.

## P04 implementation verification

P04 adds validation of the existing platform’s signed identity at the service boundary, a framework-independent `Principal`, explicit advertising permission mapping, FastAPI authorization/seller-context dependencies, and a tenant-scoped repository lookup convention. The initial adapter accepts only configured HS256 identities and checks signature, issuer, audience, expiry, UUID claims, roles, and permissions. A platform-admin flag does not bypass permissions or tenant scope.

Before serving a protected route, configure `IDENTITY_JWT_ISSUER`, `IDENTITY_JWT_AUDIENCE`, and `IDENTITY_JWT_HS256_SECRET` through protected environment configuration. The template intentionally leaves all three blank; no platform identity value was invented or written to the local `.env`. The optional Compose app profile passes them explicitly, while isolated test and container fixtures use synthetic values only.

The supplied TESTING P04 and VALIDATION P04 prompts pass: 44 focused identity/permission/tenant tests, 302 default tests, 17 disposable PostgreSQL tests, 3 isolated container tests, Ruff, formatting, and strict mypy. Adversarial testing fixed malformed verifier output and invalid direct seller-context construction. See the [P04 validation report](docs/architecture/p04-validation.md) and [P04 learning document](docs/learning/P04-identity-tenant-authorization.md).

Compose evaluates variable interpolation for every service before applying profiles. Therefore `docker compose up -d --wait postgres redis` needs only `POSTGRES_PASSWORD`; missing app settings no longer block local dependency startup. The optional `app` profile receives blank missing values and the typed application configuration rejects them at startup, so configure all database, business, and identity fields before running `docker compose --profile app up`.
