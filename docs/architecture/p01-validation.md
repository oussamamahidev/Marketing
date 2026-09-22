# P01 testing and validation

```text
Implementation: PASS
Unit Tests: PASS
Integration Tests: PASS
Security: PASS
Architecture: PASS
Regression: PASS
Overall: PASS
```

Review date: 2026-09-20. This applies the supplied P01 testing and validation prompts to the repository foundation. It includes the mandatory [P01 learning document](../learning/P01-project-foundation.md). It does not certify future business endpoints or persistence.

## Evidence

| Check | Result |
|---|---|
| `uv run --locked python -c 'import marketing_ai'` | PASS; isolated subprocess import outside the repository is also tested |
| `uv run --locked ruff check .` | PASS |
| `uv run --locked ruff format --check .` | PASS |
| `uv run --locked mypy src tests` | PASS, strict configuration |
| `uv run --locked pytest -q` | PASS: 69 tests, 3 explicitly deselected container cases |
| `uv run --locked pytest -q -m container` | PASS: all 3 real Docker cases; non-container tests deselected |
| Runtime build/import/HTTP/security | Actual image built from the runtime target; actual Uvicorn startup and HTTP responses checked without external networking |
| Build context secrecy | Real separate probe build rejects included root/nested environment files, a key canary and test fixtures; application source must remain available |
| Mandatory learning document | All 24 sections present; files, exact symbols, actual flows, tests, limitations and commands explained |

Both pytest selections are required. No test is silently skipped when Docker is unavailable; the explicit container selection fails in that situation. Registry access or cached artifacts may be required for image construction. The sandbox run used a temporary uv cache and authorized Docker access. The local builder emitted a legacy-builder notice; image builds completed successfully.

## Findings and fixes

The README's original unconditional `.env.example` copy could overwrite an already configured local `.env`. Setup now copies only when the local file is absent. `test_readme_setup_preserves_existing_local_env` proves initial creation and preservation on a repeat run. The real local password and existing PostgreSQL volume were not changed by these tests.

New test assumptions were corrected without changing production behavior: Compose profiles must be selected explicitly to render the optional app; an offline lock drift can fail because resolver metadata is absent, so the test first proves the unchanged lock works and then checks failure plus byte-for-byte lock preservation after drift. This is not represented as a specific diagnostic guarantee.

There were no proven defects in `create_app()` or the runtime image requiring production-code changes. No authentication, domain, Meta, AI or database business functionality was added. All P00 regression tests remain present.

## Test-category applicability

| Category | Applies / evidence / limits |
|---|---|
| Import and factory | Applies: installed package imports outside the checkout; missing/invalid settings and trapped network calls do not prevent construction; app instances have separate state |
| Container build | Applies: real Docker runtime build, import, UID/ownership, minimal HTTP and context-exclusion tests; no textual Dockerfile assertion substitutes for execution |
| Invalid identifiers/malformed payloads | Applies to absent paths: synthetic cross-seller/admin paths and malformed input return safe default 404. No resource schema or seller lookup exists to validate yet |
| Missing/empty configuration | Applies to Compose: missing and empty password fail through the real parser. Python startup has no mandatory settings until P02; tests prove P01 does not require them |
| Schema/lock drift | Applies to package metadata: valid lock accepted, drift rejected offline without rewriting it; metadata/source package inputs use temporary copies |
| State transitions | Business states not applicable because P01 creates no state machine. P00 document-state checks still run |
| Budget/page/text boundaries | No policy, pagination or instruction endpoint exists, so runtime boundary tests do not apply. P00 tests retain the central constants' consistency checks |
| Authentication/permissions/tenants/admin | Default documentation is public; business/admin handlers are absent. Route inventory and no-echo 404 checks apply. Claiming 401/403/RBAC enforcement would invent behavior before P04 |
| Dependency timeout/connection failure | Network connection attempts are trapped during import/construction and the real server runs without external networking. No provider call exists, so rate-limit, credential-expiry or partial-mutation simulations do not apply |
| Concurrency/idempotency | Independent factory instances are tested. No persisted mutation/constraint exists to race-test; idempotency and transaction semantics are later-phase requirements |
| Database tests | No repository, migration or model exists, so real PostgreSQL transaction/constraint tests have no implementation to exercise. Local services previously started for setup are left intact; their existence is not presented as database-feature testing |
| Redis/Celery | No client or task exists; only real Compose configuration is checked. Redis is configured as disposable. No mock is presented as queue integration evidence |
| Secrets | Blank template, real Git ignore behavior, no app credential injection, synthetic Docker context canaries, no development packages in runtime, and non-root/read-only execution are checked |
| LLM/Meta/internal-service mocks | Not applicable: no adapters or calls exist. No invented mocks or AI evaluation PASS is recorded |
| Regression | Both suites run; all prior P00 checks remain. New docs participate in existing link/reference checks |
| Coverage | Runtime factory has no business/security-policy branches. Evidence targets actual packaging/configuration/HTTP/container behavior instead of an invented domain-coverage percentage |

## Senior review

| Area | Finding |
|---|---|
| Implementation correctness | Installed src package, factory invocation, locked environment, exact commands, local services and container baseline match P01 |
| Unit tests | Exercise real installation/configuration behaviors with negative inputs; test helpers have bounded subprocess timeouts |
| Integration/contract/API | Actual Docker build/server plus in-process ASGI/lifespan checks. No provider contract is implemented or claimed |
| Dependency direction | Only the composition/presentation entrypoint exists; no database, network or business work happens during import |
| Authentication/authorization | No sensitive route exists; public docs and safe absence are explicit. Future authorization is not treated as complete |
| Security | Non-root and immutable package ownership are tested, context has allowlisted inputs, Compose credentials stay out of the app, and local ports bind to loopback |
| Idempotency/transactions | No feature mutates persistent state. Test resources are uniquely owned and cleaned up; user's services/volumes are untouched |
| Failure/ambiguity | Locked/configuration failures are explicit. There is no external financial write whose result could be ambiguous |
| Logs/metrics | No business/external-call instrumentation needed in P01. Default server logs exist; structured correlation/error infrastructure is still P02 work |
| Performance | No application query, list operation or service polling exists, so N+1/full scans are not relevant. Import/factory remain lightweight |
| Docs/migrations | README commands are accurate, `.env` setup is repeat-safe, learning document describes actual behavior, and no migration is appropriate |
| Regression risk | Changes add tests/marker/documentation only in this follow-up; product code remains the minimal verified factory |

There is no initialized Git index in this workspace. Security review therefore covers intended repository/distribution inputs and ignore behavior, not a claimed scan of nonexistent Git history. The actual ignored `.env` is never read by the test suite or copied into its build contexts. Dependency locks improve repeatability but do not constitute a vulnerability audit or a permanent security guarantee.

## Gate

P01 implementation, testing, validation and learning documentation are complete for the stated foundation scope. No critical failure remains. **P02 may proceed.** Future endpoints and services must implement their own applicable safety, configuration, security and recovery requirements.
