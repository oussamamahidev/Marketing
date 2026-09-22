# ADR-004: Use Celery and Redis before considering Temporal

Status: Accepted architecture baseline for MVP.

## Document responsibility

Purpose: record background-job ownership and workflow-engine replacement criteria. Owns dispatch/retry principles, not task implementations or cadence values. Depends on [project context](../../PROJECT_CONTEXT.md), [business constants](../../BUSINESS_CONSTANTS.md), and [PostgreSQL ADR](ADR-002-postgresql.md). Used by P12/P13/P15/P23 and optional P27. Tested by P00 review and later duplicate-task, queue-loss, retry, reconciliation and restore scenarios.

## Context

The MVP needs performance synchronization, reconciliation scans and recommendation jobs. External writes can be ambiguous, but introducing another durable workflow platform does not remove approval or provider reconciliation requirements.

## Decision

Use Celery with Redis for scheduled/background execution. A task is a wake-up mechanism for an application use case, not business authority. PostgreSQL stores pending intent, execution steps/results, audit and recovery eligibility. Pass safe identifiers and correlation metadata in tasks, never OAuth tokens or whole sensitive payloads.

Assume tasks may be duplicated, delayed or lost. Reconstruct pending work from durable intent, claim it transactionally and recheck seller/action scope. Scope idempotency to the business operation, not the Celery task ID. Periodic reconciliation follows the named scan/stale constants; safe write retries follow MAX_RETRIES_META_WRITE with exponential backoff and jitter. Unknown outcomes are reconciled before any retry; approval expiry and dispatch revalidation still apply.

P12 defines safe durable execution; P13 implements reconciliation/recovery; P15 adds the common Celery scheduling/worker runtime. Earlier phases must leave uncertain writes blocked even if scheduled recovery has not yet been implemented. Redis loss cannot turn a consumed approval into a new spend authorization.

## Alternatives

- Temporal at MVP start: strong durable orchestration capabilities, but adds service operations, SDK/workflow constraints and deployment complexity before proven need.
- FastAPI in-process background tasks as the sole queue: cannot establish durable job recovery across restarts.
- Cron without durable operation tracking: schedules work but does not solve duplicate delivery or ambiguous effects.

## Consequences

Initial operations stay aligned with the existing Python/Redis stack. Engineering must explicitly implement durable intents, idempotent handlers, reconciliation, safe retries and monitoring. Complex long-lived branching workflows may eventually exceed the maintainability of this approach. Celery does not supply exactly-once financial execution.

## Replacement Trigger

Consider Temporal only when observed long-running workflows with durable timers, approvals, branching and compensations create repeated recovery incidents or unacceptable bespoke state-management complexity despite the current design. Require concrete incident/maintenance evidence, an operational owner, a migration plan for in-flight executions, and a proof that approval, tenant isolation and reconciliation invariants remain intact. Optional P27 and a new ADR authorize that transition; merely needing retries or background jobs does not.
