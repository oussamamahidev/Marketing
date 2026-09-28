# P05 — Advertising Domain Model, Policies, and Campaign Lifecycle

## 1. What We Built

P05 adds the framework-independent advertising bounded context. It models seller-owned marketing facts, immutable money and payload values, deterministic eligibility and budget rules, approval checks, and the campaign lifecycle. It does not add HTTP routes, database tables, Meta calls, AI calls, or repository implementations.

## 2. Objectives of This Phase

The phase makes the rules that protect spend explicit and testable before an application use case or external gateway exists. A later phase must call these policies before it persists or dispatches a financially sensitive action.

## 3. Files Created

| File | Responsibility |
|---|---|
| `domain/advertising/enums.py` | Stable lifecycle, policy, approval, and domain-error codes. |
| `domain/advertising/value_objects.py` | Immutable `Money`, `DailyBudget`, and `PayloadHash`. |
| `domain/advertising/entities.py` | Seller-scoped advertising facts and immutable aggregates. |
| `domain/advertising/policies.py` | Deterministic eligibility, budget, ownership, publication, CTA, and approval decisions. |
| `domain/advertising/services.py` | Explicit state transitions and approval-request construction. |
| `domain/advertising/repositories.py` | Seller-scoped persistence protocols only. |
| `docs/architecture/campaign-state-machine.md` | The lifecycle contract. |
| `tests/unit/domain/` | Pure, adversarial domain tests. |

## 4. Files Modified

P05 does not alter routes, migrations, configuration loading, database code, or identity behavior. This learning document and the README checkpoint document the completed phase.

## 5. Architecture Explanation

The domain depends only on Python standard-library types and other domain modules. It has no FastAPI, SQLAlchemy, Meta, MCP, Redis, database, or LLM import. Application code will compose typed settings into `AdvertisingPolicyConfig`, call domain policies, then use repository and gateway ports.

## 6. Request / Data Flow

```text
HTTP or worker
    -> application use case
    -> AdvertisingPolicyConfig + domain policy
    -> seller-scoped repository / Meta gateway
    -> durable execution and audit record
```

The domain stops at the decision. It does not fetch stock, call Meta, or write a database.

## 7. Theory You Need to Understand

A domain model expresses business facts and invariants without knowing where data is stored or how requests arrive. A value object represents a validated value. An entity represents a seller-owned fact with an identity. A policy evaluates deterministic rules and returns a stable, machine-readable decision.

## 8. Practical Implementation Explanation

`CampaignDraft` starts in `DRAFT`, is immutable, and can change state only through `transition_campaign`. The service looks up a `(state, trigger)` pair in `CAMPAIGN_TRANSITIONS`; absent pairs raise `INVALID_STATE_TRANSITION`. This makes an ambiguous external result an explicit `RECONCILIATION_REQUIRED` state.

## 9. Important Classes, Functions, Interfaces, and Schemas

- `Money` stores integer centimes and accepts only finite `Decimal` inputs for conversion.
- `DailyBudget` requires positive `Money`.
- `PayloadHash` is a SHA-256 digest of canonical bytes.
- `AdvertisingPolicyConfig` receives same-named typed business constants.
- `product_eligibility()` combines stock, margin, cancellation, and return decisions.
- `validate_daily_budget()` enforces the per-campaign and seller-total ceiling.
- `validate_exact_payload_approval()` binds approval to seller, campaign, expiry, and one hash.
- Repository protocols make every lookup accept `seller_id`.

## 10. Database Changes

None. P05 defines repository protocols but deliberately does not create an advertising persistence model, migration, or transaction implementation. PostgreSQL remains the future authoritative implementation boundary.

## 11. API Changes

None. There are no new routes or request schemas. HTTP parsing, authentication, and canonical error mapping remain outside this domain package.

## 12. Security Considerations

Financial rules are deterministic code, not AI output. Seller ownership is checked by UUID equality. Approval requires an approved, unexpired record for the same seller, campaign, and exact payload digest. A payload change cannot reuse an old approval. The domain stores only an opaque Meta identity reference, never an OAuth token.

## 13. Error Handling

Domain failures use stable `DomainErrorCode` values, including invalid value objects, policy configuration, ownership violations, invalid approvals, and invalid state transitions. Application or presentation code later translates them to canonical API errors with request IDs.

## 14. Testing Strategy

The domain tests use no network, database, Redis, Meta gateway, FastAPI route, or LLM. They exercise allowed and forbidden lifecycle transitions, Decimal conversion, minimum/maximum/above-maximum budgets, seller ceilings, product reason codes, low-confidence samples, tenant mismatch, CTA denial, expiry, and exact-payload approval.

## 15. Commands Used

```bash
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked mypy src tests
uv run --locked pytest -q
uv run --locked pytest -q tests/security tests/api
uv run --locked pytest -q -m database
uv run --locked pytest -q -m container
```

## 16. How to Test It Manually

Run `uv run --locked pytest -q tests/unit/domain`. To inspect the lifecycle, open [the state machine](../architecture/campaign-state-machine.md). The test names show concrete examples: a draft cannot execute directly; a seller cannot use another seller’s resource; and changing canonical payload bytes invalidates approval.

## 17. Design Decisions

The state table is immutable and separate from entities so it is easy to audit. Policy configuration uses field names matching centralized business constants but does not import `Settings`; composition remains an application concern. CTA combinations are supplied as an explicit mapping because no business-constant table yet defines product-wide combinations.

## 18. What I Should Learn From This Phase

Keep business decisions near the data they protect, make state transitions finite and explicit, preserve exact monetary values, and represent uncertainty honestly. A timeout after a write is not evidence of either success or failure; it requires reconciliation.

## 19. Interview Questions From This Phase

1. Why use integer centimes instead of floats for budgets?
2. Why is a state-transition table safer than setting a status field directly?
3. What makes an approval exact-payload approval?
4. Why should seller scope be an argument to every repository lookup?
5. Why does an external timeout lead to reconciliation rather than a retry?

## 20. Common Mistakes

Do not compare money with binary floats, permit low-order samples to pass rate checks by default, accept changed payloads under an existing approval, combine proposal and execution status into one ambiguous field, or let an LLM decide stock, budget, or permission rules.

## 21. Debugging Guide

For a rejected policy, inspect `PolicyDecision.reason_codes`; do not infer a reason from display text. For a lifecycle failure, inspect the current `CampaignState` and requested `CampaignTrigger` against the documented table. For approval failure, separately check scope, approval status, expiry, and `PayloadHash` equality.

## 22. Connection to Previous Phases

P02 supplies the typed, centralized settings from which the policy configuration will be composed. P03 supplies the future PostgreSQL transaction and migration foundation. P04 supplies verified seller context and authorization; P05’s repository protocols preserve that seller scope for advertising resources.

## 23. Preparation for the Next Phase

A subsequent application/persistence phase must map `Settings` into `AdvertisingPolicyConfig`, implement the seller-scoped repository protocols with PostgreSQL, enforce optimistic/concurrent updates, persist canonical payloads and approval evidence, and revalidate policy immediately before any Meta mutation.

## 24. Final Phase Summary

P05 establishes deterministic, framework-independent foundations for safe advertising actions. Testing found and fixed two fail-closed input guards: a negative active-budget aggregate is rejected, and malformed snapshot order counts return a typed domain error instead of leaking a raw `TypeError`. On 2026-09-28, validation passed with 13 focused domain tests, 315 default tests, 81 security/API tests, 17 disposable PostgreSQL tests, isolated Docker regression tests, Ruff, formatting, and strict mypy.
