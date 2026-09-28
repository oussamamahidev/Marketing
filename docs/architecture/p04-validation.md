Implementation: PASS
Unit Tests: PASS
Integration Tests: PASS
Security: PASS
Architecture: PASS
Regression: PASS
Overall: PASS

# P04 testing and validation

Review date: 2026-09-22. This report applies the supplied TESTING P04 and VALIDATION P04 prompts to identity verification, tenant context, RBAC, ownership helpers, their configuration, and their tests.

## Evidence

| Check | Result |
|---|---|
| Focused identity, API and tenant tests | 44 passed after adversarial additions |
| `uv run --locked pytest -q` | 302 passed; 20 marked database/container tests deselected |
| `uv run --locked pytest -q -m database` | 17 passed against disposable PostgreSQL |
| `uv run --locked pytest -q -m container` | 3 passed using isolated image resources |
| Ruff and format check | PASS |
| `uv run --locked mypy src tests` | PASS, 44 source/test files |

## Findings resolved during testing

### Malformed identity-adapter output

**Problem:** a replacement verifier could return an arbitrary object despite its typed interface, causing permission evaluation to raise an accidental 500.

**File:** `src/marketing_ai/api/dependencies.py`

**Root cause:** the HTTP integration boundary trusted the adapter's static return annotation without a runtime `Principal` check.

**Required fix:** validate the returned object is a `Principal`; otherwise return canonical `UNAUTHENTICATED`.

**Test that proves the fix:** `test_malformed_verifier_response_fails_closed_as_unauthenticated` injects a verifier returning an arbitrary object and now receives 401 with no token disclosure.

### Invalid direct seller context

**Problem:** direct construction of `SellerContext` accepted a non-UUID seller identifier.

**File:** `src/marketing_ai/domain/identity/principal.py`

**Root cause:** only `from_principal()` validated its input; the value object itself did not enforce its identifier invariant.

**Required fix:** add `SellerContext.__post_init__()` UUID validation.

**Test that proves the fix:** `test_seller_context_rejects_an_untyped_or_invalid_tenant_identifier` now raises `ValueError`.

## Acceptance review

- HTTP dependencies, rather than routes, parse and verify bearer tokens.
- The signature, fixed HS256 algorithm, canonical base64url encoding, issuer, audience, expiry, UUID claims, duplicate JSON claims, role/permission vocabulary, and platform-admin boolean are adversarially tested.
- Missing/invalid credentials produce 401; valid identities without the declared permission produce 403.
- The role matrix and explicit `ads.admin` dependency are covered. The platform-admin flag provides no implicit permission or cross-tenant bypass.
- `SellerScopedLookup.get_for_seller(*, seller_id, resource_id)` requires tenant scope. Foreign and missing IDs both produce scoped 404, and tests prove a platform-admin flag cannot disclose another seller's resource.
- Raw token text is absent from the canonical response and captured application output. The safe logging formatter's header/message redaction remains covered by P02 regression tests.
- P04 adds no persistent identity/resource model, repository implementation, state transition, mutation, idempotency key, rate limit, remote identity call, LLM/Meta call, or financially sensitive step. Therefore P04-specific database constraints, transaction/concurrency/idempotency, external timeout/connection/partial-success simulation, rate-limit behavior, AI mocks, numeric business boundaries, and new metrics are not applicable. The real PostgreSQL and container suites still ran to prove regression safety. Future remote identity adapters must add explicit timeout/dependency translation and low-cardinality latency/outcome metrics at that adapter boundary.
- No P04 migration is needed because the phase adds no schema. Documentation now records the validation evidence and remaining platform identity contract work.

## Gate

P04 implementation, testing, validation, and learning documentation pass. The next implementation prompt may proceed.
