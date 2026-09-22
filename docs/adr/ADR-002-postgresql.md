# ADR-002: PostgreSQL is the local authoritative store

Status: Accepted architecture baseline for MVP.

## Document responsibility

Purpose: record local persistence authority and analytics evolution. Owns durable-state rules, not schemas/migrations or retention values. Depends on [project context](../../PROJECT_CONTEXT.md), [business constants](../../BUSINESS_CONSTANTS.md), and [overview](../architecture/overview.md). Used by P03, P09–P16, P19 and P23. Tested by P00 review and subsequent PostgreSQL transaction, concurrency, recovery and analytics tests.

## Context

Approvals, execution intent, budget reservations and audit evidence must survive crashes and support atomic decisions. Redis queues/caches and LLM workflow checkpoints cannot independently establish whether an external financial action is authorized or has happened.

## Decision

Use PostgreSQL with SQLAlchemy async persistence and Alembic migrations for local business state. Application use cases own transaction boundaries through ports; Infrastructure owns ORM models and repositories. Store money as integer centimes. Include seller scope in lookup predicates, uniqueness rules and tenant-owned relationships so cross-tenant references cannot bypass service checks.

Commit approval consumption, execution identity, seller budget reservation, audit and durable dispatch intent together before sending a financial mutation. Dispatch externally outside a long-lived transaction and persist/reconcile the result afterward. Do not claim distributed atomicity with Meta. PostgreSQL unavailability blocks new financial dispatch.

Redis remains ephemeral coordination, cache and Celery transport. Loss of Redis must not lose the authoritative execution history or permit duplicate authorization. Store any resumable workflow checkpoint durably with tenant scope, while keeping domain approval/execution records independently authoritative. Commerce systems remain authoritative for their facts and Meta for remote state.

Initially query performance/commerce snapshots in PostgreSQL, with appropriate indexes, bounded reporting, retention, and workload measurement. Use configured backup/recovery objectives and prove restore by test.

## Alternatives

- Redis as business authority: fast, but conflicts with durable transactional audit and recovery requirements.
- Document/event stores for all state: possible, but introduce extra modeling/consistency work without an established MVP need.
- Specialized analytical storage immediately: adds synchronization, cost, operations and source-of-truth ambiguity before measured demand.

## Consequences

Transactional guarantees protect local invariants, but require careful indexes, lock order, concurrency tests and migration planning. Persisted intent and reconciliation remain necessary for external writes. Reporting workload must not starve approval/execution transactions. Operational restore includes reconciling remote actions that occurred after the restored database point.

## Replacement Trigger

Add specialized analytical storage when measured reporting volume/latency or resource contention continues to violate agreed targets after query/index tuning, retention/partitioning and sensible read isolation. Require a replayable export, tenant-aware access controls, provenance/freshness, deduplication and reconciled totals. It becomes an analytical projection, not authority for approvals, budgets or execution. Replacing the transactional store itself requires a separate ADR proving equivalent safety and recovery guarantees; no such replacement is planned for MVP.
