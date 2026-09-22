# ADR-006: Require exact-payload human approval for external mutations

Status: Accepted, mandatory MVP safety invariant.

## Document responsibility

Purpose: define human authority over financial intent. Owns approval binding, consumption and invalidation requirements, not UI implementation or policy values. Depends on [project context](../../PROJECT_CONTEXT.md), [business constants](../../BUSINESS_CONSTANTS.md), and [overview](../architecture/overview.md). Used by P09–P14/P18/P19 and future automation work. Tested by P00 review and later payload-tampering, replay, expiry, authorization, race and failure-injection tests.

## Context

LLM proposals can be incorrect or manipulated by untrusted input. Even a valid approved proposal may become unsafe when stock, permissions, budget or account state changes before dispatch. Human approval must identify the actual intended mutation rather than a vague instruction to optimize advertising.

## Decision

Every external advertising write requires authorization, deterministic policy validation, exact-payload human approval, idempotency and audit. This includes publication, activation/resume, pause and budget/schedule changes. Automatic low-stock behavior is a recommendation; STOCK_FLOOR_TO_AUTO_PAUSE does not authorize an automatic pause. BUDGET_CHANGE_REQUIRES_APPROVAL is immutable true.

Persist the approver, verified seller/account, action, proposal revision, canonical effective payload and digest/schema version, validation/policy version, grant/expiry times and execution consumption. The canonical representation covers every effective mutation field, including approved defaults and creative version. If an effective field changes, invalidate the approval and request a new one.

Before dispatch, revalidate current permissions, ownership, stock, budget including reservations, approval expiry, account currency/access and kill switch. Unavailable authoritative facts fail closed. Transactionally bind one approval to one execution, append audit and persist dispatch intent. Concurrent attempts cannot consume the same approval for different operations. A graph resume, chat statement or task redelivery never creates approval.

Use APPROVAL_PAYLOAD_TTL_MINUTES for expiration. Once a send may have occurred, expiry does not prevent read-based reconciliation, but it does not authorize a different mutation or a fresh send after expiry. Approved intent and provider effects remain separate durable records. An admin kill switch blocks future dispatch; it is not a backdoor unapproved remote pause or cancellation.

## Alternatives

- Automatically execute model recommendations: violates the human-authority invariant and exposes spend to unreliable inputs.
- Approve an entire strategy or mutable draft: allows effective payload changes outside the reviewed decision.
- Treat initial policy validation as sufficient: misses current stock, permissions and concurrent budget changes.
- Use a UI confirmation without a durable record: cannot safely audit, replay-protect or recover execution.

## Consequences

Sellers perform an explicit review step and may need to reapprove when the payload or approval validity changes. Durable records and concurrency controls add complexity, but financial authority is testable and attributable. Low-stock situations produce urgent recommendations while existing remote spend continues until an authorized approved action is executed; the UI must make this limitation clear.

## Replacement Trigger

There is no MVP replacement trigger that removes human approval or makes an LLM authoritative. A future automation proposal requires a new explicit product/security decision and ADR, narrowly bounded prior authorization, deterministic policies, revocation, audit and equivalent recovery guarantees. Optional P26 remains recommendation-first and does not itself waive approval. UX or storage implementation may evolve only while preserving exact-payload binding and all mutation invariants.
