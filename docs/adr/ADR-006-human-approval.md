<!--
PURPOSE: Record the mandatory approval and revalidation model for financially sensitive Meta mutations.
RESPONSIBILITY: Governs authorization-to-mutation safety controls; it does not define every future campaign policy threshold.
DEPENDENCIES: Trusted identity, deterministic policies, PostgreSQL authority, and Meta gateway contracts.
USED BY: Proposal, approval, publication, audit, reconciliation, and admin-safety implementation.
TESTED BY: P00-T ADR review and later domain/security/integration/e2e tests.
-->

# ADR-006: Require exact-payload human approval for sensitive writes

**Status:** Accepted — P00 architecture baseline

## Context

Creating, activating, or materially changing a Meta campaign can spend seller money and affect inventory/fulfillment operations. Inputs and external state can become stale after AI generation, and LLM output is not authoritative. A high-level approval or standing permission cannot show what the seller actually approved or safely authorize a changed campaign.

## Decision

Before any financially sensitive Meta write, the system must:

1. authorize the principal and seller scope;
2. run deterministic policy validation;
3. materialize an immutable exact payload revision with a canonical hash, policy-relevant source versions, scope, and expiry;
4. record an explicit seller approval bound to that revision;
5. persist idempotency intent and audit evidence;
6. immediately revalidate permission, ownership, stock, budget limits, approval validity, kill-switch state, and current policy before dispatch; and
7. invoke the Meta gateway through a reconcilable execution record.

Any material payload or policy-relevant context change invalidates approval. If authoritative persistence is unavailable, the mutation fails closed. An ambiguous external result remains ambiguous until reconciliation establishes an outcome.

## Alternatives considered

| Alternative | Why it was not selected for the MVP |
| --- | --- |
| Auto-publish LLM output | Gives untrusted probabilistic output financial authority. |
| Approve a mutable high-level recommendation | Does not bind the seller decision to the actual external payload. |
| Broad standing approval without exact payload binding | Cannot safely capture context changes, limits, or accountability. |

## Consequences

- The system has strong accountability, reproducibility, tenant safety, and a clear audit trail.
- Seller experience must support review, expiry, rejection, resubmission, and explanations for invalidated approvals.
- Persistence, policy evaluation, idempotency, worker recovery, and reconciliation become first-class implementation work.
- A successful approval is necessary but never sufficient; current conditions are checked again immediately before mutation.

## Replacement trigger

There is no convenience- or volume-based exception. A future ADR may permit a narrowly defined low-risk automated action only after explicit product, security, legal, and operational approval, with hard limits, deterministic policy, authorization, idempotency, audit, reconciliation, monitoring, and a kill switch.

Campaign creation and budget-changing actions retain exact-payload approval unless formally superseded by that ADR. Recommendation-first automation is optional future work and cannot weaken this decision by implication.
