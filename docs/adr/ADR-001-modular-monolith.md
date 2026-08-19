<!--
PURPOSE: Record why the MVP is delivered as a modular monolith.
RESPONSIBILITY: Governs service shape and dependency boundaries; it does not select future service extraction details.
DEPENDENCIES: P00 architecture overview and product scope.
USED BY: P01-P24 implementation, deployment, and future architecture reviews.
TESTED BY: P00-T ADR review and P00-V acceptance validation.
-->

# ADR-001: Start with a FastAPI modular monolith

**Status:** Accepted — P00 architecture baseline

## Context

The MVP has one tightly connected product goal: safely turn seller-authorized commerce context into Meta campaign proposals, approvals, executions, analytics, and recommendations. Its boundaries are still evolving and it needs consistent tenant isolation, transactional approval/execution records, straightforward observability, and low operational overhead.

Starting with distributed services would introduce network failure modes, distributed authorization, duplicate data ownership, cross-service transactions, more deployments, and operational complexity before the product has evidence that these costs are justified.

## Decision

Build one Python/FastAPI modular monolith with the dependency direction:

~~~text
Presentation -> Application -> Domain <- Infrastructure
~~~

Modules communicate through narrow typed contracts inside one deployable codebase. HTTP routes and Celery workers call application use cases; the domain remains independent of frameworks and integration SDKs. The MVP does not introduce microservices, Kafka, Kubernetes, or a service mesh.

## Alternatives considered

| Alternative | Why it was not selected for the MVP |
| --- | --- |
| Microservices from the start | Premature distributed data, authorization, deployment, and failure-management complexity. |
| Serverless/functions per workflow | Fragments ownership of stateful approval and reconciliation flows and complicates local development/observability. |
| Unstructured single-layer application | Faster initially but fails to protect business policy from framework and integration concerns. |

## Consequences

- Delivery, debugging, testing, transactional consistency, and deployment remain simpler.
- Explicit module boundaries remain mandatory; a monolith is not permission for routes, workers, or integrations to bypass application/domain contracts.
- Components initially scale together, so runtime measurements and module ownership must be tracked.
- Any internal module still enforces tenant scope, auditability, idempotency, and fail-closed mutation rules.

## Replacement trigger

Extract one selective service only when measured evidence demonstrates all of the following:

1. a bounded capability has stable contracts and clear data ownership;
2. it needs independent ownership, release cadence, scaling, credential isolation, or reliability treatment; and
3. those needs cannot be met inside the monolith without repeated SLO breaches, harmful coupled releases, or unacceptable operational risk.

The extraction must be preceded by a new ADR covering data ownership, authorization, audit continuity, idempotency, observability, rollback, and migration. A broad rewrite is not a replacement strategy.
