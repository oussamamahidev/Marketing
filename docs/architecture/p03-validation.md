# P03 testing and validation

```text
Implementation: PASS
Unit Tests: PASS
Integration Tests: PASS
Security: PASS
Architecture: PASS
Regression: PASS
Overall: PASS
```

Review date: 2026-09-21. P02's supplied formal gates passed before this work.

This report applies the supplied TESTING P03 and VALIDATION P03 prompts. The implementation safely rejects missing operational database inputs rather than inventing deployment defaults. Those values remain a deployment prerequisite documented in BUSINESS_CONSTANTS section 11, not a defect in the persistence foundation.

## Evidence

| Check | Result |
|---|---|
| `uv run --locked pytest -q` | 254 passed; real database/container selections explicitly deselected |
| `uv run --locked pytest -q -m database` | 17 passed against disposable PostgreSQL, separate database per test |
| `uv run --locked pytest -q -m container` | 3 passed: actual build, non-root/read-only runtime, HTTP and context exclusion |
| `uv run --locked ruff check .` and format check | PASS |
| `uv run --locked mypy src tests` | PASS, 33 files; explicit package bases/source path retain strict checking with nested conftest modules |
| `uv run --locked mypy src tests migrations` | PASS, 35 files including migration environment and baseline revision |
| Fresh migrations | Smoke upgrade, repeat upgrade, metadata drift check, downgrade/base and re-upgrade pass; only Alembic's version table exists |
| Multiple heads | Synthetic branch is rejected before changing an empty database |
| URL secrecy | Percent-encoded synthetic password survives Alembic without ConfigParser interpolation; safe configuration and migration errors omit URL/input values |
| Learning documentation | [P03-postgresql-persistence.md](../learning/P03-postgresql-persistence.md), 24 sections and final testing updates |

Docker socket and local network access required authorized execution outside the sandbox. Initial test setup exposed PostgreSQL's temporary initialization socket as ready before the final TCP server started; the fixture now waits specifically for TCP readiness. All test-owned containers/databases are removed. No local `.env`, existing service, volume or production database is modified by the tests.

## Findings resolved during testing

### Alembic hid its own safe diagnostic

**Problem:** a rejected database connection made Alembic fail, but the intended fixed diagnostic was replaced by an unhelpful `external_log` event. **File:** `migrations/env.py`. **Root cause:** the migration environment installed the application runtime formatter, whose intentional allowlist discards arbitrary third-party log messages, including Alembic's controlled `CommandError` text.

**Fix:** the migration environment no longer reconfigures application logging. It still catches every migration exception and raises the fixed credential-free `CommandError`. **Proof:** the new real PostgreSQL subprocess case points Alembic to an unavailable URL containing a password canary. It asserts the fixed error text is present in Alembic output and the canary is absent. The command's normal output stream is accepted because Alembic writes its `FAILED:` diagnostic there.

### Session dependency without lifespan

The health dependency already failed closed when lifespan was absent, but `get_session()` would have raised an attribute error. It now returns the same controlled dependency-unavailable result. The new ASGI test proves this gives canonical 503 rather than an accidental 500. This is a defensive boundary fix; no endpoint, schema or business behavior was added.

## Acceptance and architecture

| Requirement | Evidence |
|---|---|
| Fresh database migrates to head | Actual PostgreSQL upgrade plus inspected `alembic_version`; one no-op baseline revision establishes lineage without business tables |
| Failed use case rolls back | Insert then application exception leaves no row; same session starts a later transaction successfully |
| Partial failure rolls back | Real primary-key violation rolls back the first insert too; no mock substitutes for PostgreSQL constraints |
| Cancellation cleans up | A cancelled transaction leaves no row and the pool supports a later readiness query |
| No shared concurrent session | Two simultaneous worker-style scopes and two real ASGI dependency invocations receive distinct session objects |
| Bounded pool | Hold configured pool plus overflow capacity, observe acquisition timeout, fail readiness, release sessions and recover |
| Availability | Live PostgreSQL returns ready; refused TCP and rejected credentials return safe dependency 503 while liveness stays 200 |
| Session cleanup without hidden commit | Closing an uncommitted session leaves no persisted row |
| Transaction ownership | Application helper commits/rolls back; nested/pre-existing transactions are rejected. Repositories must not commit |
| Lifecycle | Engine constructed in lifespan, no import/startup connection required; shutdown disposes it. Missing lifespan returns failed readiness |
| Metrics | Database readiness and transaction outcome/latency metrics use fixed labels; readiness counter/histogram observed against PostgreSQL |

Infrastructure owns SQLAlchemy, database lifecycle and transaction mechanics. Core settings parse typed connection inputs; API dependencies acquire a fresh session and health routes only coordinate probes. No domain policy, repository, campaign, Meta or AI table was introduced. Application transaction ownership is documented but no business use case exists yet.

## Edge cases and limits

| Case | Applicability and result |
|---|---|
| Missing/invalid configuration | New required fields join existing missing-field tests; malformed/unsupported URLs, absent credentials, zero pool/timeouts and negative overflow fail |
| Missing resource | No business repository lookup exists; existing API 404 tests remain applicable |
| Stale connections | Pool pre-ping is enabled; actual pool exhaustion/recovery is tested. This is not a guarantee about every network partition or failover topology |
| Duplicate calls | Repeated migration upgrade to head is a no-op. Business idempotency is not implemented by this foundation |
| Timeout/unavailable/expired credentials | Real refused connection, pool timeout and rejected synthetic credentials exercise fail-closed readiness. No automatic DB write retry exists |
| Malformed dependency result | The earlier pluggable readiness contract tests remain. PostgreSQL health runs a fixed `SELECT 1`, not an untrusted provider payload |
| Concurrent update | Actual transaction visibility, uniqueness failure and separate concurrent sessions are covered using test-only tables. Business optimistic/pessimistic locking awaits actual aggregates |
| Partial success/cancellation | Rollback and cancelled transactions are tested. A failure during commit can have an uncertain outcome and is never reported as a guaranteed rollback |
| Tenant/permissions | No tenant-owned model or lookup exists. Test role is a non-superuser temporary DB owner; production requires a distinct restricted runtime role and DDL migration owner. No production privilege provisioning is claimed |
| Secrets/SQL injection | Runtime settings/log policy excludes raw credentials/queries; SQLAlchemy parameters preserve a malicious-looking string as data. SQL identifiers in disposable-database fixtures use driver identifier quoting |
| Schema safety | App never calls create_all or upgrades automatically. Smoke tooling refuses existing public tables/views and never drops them; run only on a disposable empty database |
| Performance | Configured finite pool/wait/connect/readiness bounds; no queries over product tables, N+1 issue, load benchmark or production capacity claim |
| Redis/LLM/Meta | No corresponding adapter/call exists; no invented service or AI test PASS |

The local operational values are deliberately unresolved. Synthetic test values live only in fixtures and do not authorize a deployment configuration. Existing P00 business values stay unchanged. Existing P00/P01/P02 behavior changes only where P03 explicitly requires a URL, bounded pool settings and mandatory PostgreSQL readiness. Historical phase reports retain their original scope. Because invalid/missing settings stop construction, this prerequisite cannot silently weaken the production contract.

The runtime image now includes reviewed Alembic artifacts but excludes tests and environment files. New migration generation belongs in the checkout; production migration execution must be a separate controlled step with migration credentials. Metrics are registered internally, without a new public endpoint or exporter deployment.

## Gate

P03 implementation, testing, validation and learning documentation pass for the stated persistence-foundation scope. Configure the five named deployment settings and host/Compose URLs through protected environment configuration before running a real app instance. This is operational setup, not permission to add code defaults. **P04 may proceed.**
