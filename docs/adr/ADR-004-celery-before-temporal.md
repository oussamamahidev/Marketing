<!--
PURPOSE: Record the MVP background-job and workflow-durability choice.
RESPONSIBILITY: Governs asynchronous execution for the MVP; it does not make Redis authoritative workflow state.
DEPENDENCIES: P00 architecture overview, PostgreSQL authority, and application use cases.
USED BY: Synchronization, retries, reconciliation, and scheduled worker implementation.
TESTED BY: P00-T ADR review and later worker/reliability tests.
-->

# ADR-004: Use Celery and Redis before Temporal

**Status:** Accepted — P00 architecture baseline

## Context

The MVP needs scheduled performance synchronization, retries, reconciliation, and background work. It does not yet have proven requirements for a separate durable workflow platform. Introducing Temporal now would increase operations, deployment, training, and workflow-model complexity before its benefits are necessary.

## Decision

Use Celery with Redis for MVP background jobs and scheduled tasks. Celery tasks invoke application use cases. PostgreSQL-backed records hold policy-relevant workflow state, idempotency keys, execution status, audit history, and reconciliation evidence; Redis is only a broker/cache/ephemeral coordination layer.

Jobs are treated as effectively at-least-once. They must tolerate duplicates, delayed delivery, partial failure, timeouts, concurrent work, and retry. They may not use Redis state as proof of a completed financial mutation.

## Alternatives considered

| Alternative | Why it was not selected for the MVP |
| --- | --- |
| Temporal from the start | Provides durable orchestration but adds premature platform and operational complexity. |
| Inline threads or in-process background tasks | Do not provide adequate resilience, visibility, or restart safety for critical jobs. |
| Kafka or custom queue platform | Outside MVP scope and does not by itself solve durable business-state management. |

## Consequences

- Scheduled sync, retry, and reconciliation can be delivered with modest operational overhead.
- Application code must persist state before and after side effects, use idempotency, classify retries, and reconcile ambiguity.
- Long-lived approval or compensation semantics remain modeled explicitly in PostgreSQL/application code rather than assumed from the task queue.
- Queue monitoring, stuck-job detection, bounded retry policy, and worker runbooks are required.

## Replacement trigger

Move selected workflows to Temporal only when long-running, multi-step work with durable timers, human-approval waits, compensation, restart/deploy recovery, or execution history cannot reliably meet SLOs using PostgreSQL-backed state plus Celery.

The trigger requires measured operational evidence, not anticipated scale. A new ADR must define which workflows move, migration/rollback, idempotency, audit continuity, tenant isolation, and how Temporal does not weaken the existing approval and fail-closed rules.
