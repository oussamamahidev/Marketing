<!--
PURPOSE: Record PostgreSQL as the authoritative operational store for the MVP.
RESPONSIBILITY: Governs authoritative persistence and analytics evolution; it does not define individual schemas or migrations.
DEPENDENCIES: P00 architecture overview and data-recovery requirements.
USED BY: Persistence, analytics, worker, and deployment implementation.
TESTED BY: P00-T ADR review and P00-V acceptance validation.
-->

# ADR-002: Use PostgreSQL as the authoritative operational store

**Status:** Accepted — P00 architecture baseline

## Context

Tenant scope, campaign proposals, approvals, exact payload versions, idempotency keys, executions, reconciliation, audit events, and policy-relevant state require durable relational transactions and recoverable history. Redis is useful for cache, queue brokering, locks, and ephemeral coordination, but it must not decide a financial or approval outcome.

## Decision

Use managed PostgreSQL as the authoritative database, with SQLAlchemy 2.x and Alembic for persistence and schema evolution. PostgreSQL stores operational state, tenant ownership, approval and execution records, audit evidence, and the source-of-truth records needed to reconcile external writes.

Redis remains non-authoritative. Loss, eviction, or replay of Redis data must not alter a final approval, execution, audit, or seller authorization decision.

## Alternatives considered

| Alternative | Why it was not selected for the MVP |
| --- | --- |
| Redis as primary state | Does not provide the required durable, relational, auditable authority for sensitive workflow decisions. |
| Document/NoSQL primary store | Adds a different consistency and query model without a demonstrated need; relational tenant-scoped workflow state is central. |
| Separate OLTP and analytical stores from day one | Duplicates data pipelines, operational burden, and reconciliation work before reporting load proves the need. |

## Consequences

- The system gains durable transactions, constraints, tenant-scoped queries, migration discipline, and recoverable audit history.
- Persistence work must define indexes, transaction boundaries, backup/restore procedures, and safe migration practices.
- Reporting queries must be designed not to harm transaction latency; snapshots and rollups can be introduced within PostgreSQL first.
- PostgreSQL remains authoritative for operational mutation state even if a future analytical store is added.

## Replacement trigger

Introduce specialized analytical storage only when measured historical-reporting retention, cardinality, aggregation latency, query concurrency, or cost materially harms transactional SLOs after indexes, partitions, rollups, and suitable replicas have been evaluated.

The analytical system must be a governed, reconcilable downstream copy. A new ADR must define ingestion freshness, correction/backfill behavior, tenant access controls, data retention, query routing, observability, and rollback. It must not become the authority for approvals or external mutations.
