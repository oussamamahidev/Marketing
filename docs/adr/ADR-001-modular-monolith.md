# ADR-001: Start with a FastAPI modular monolith

Status: Accepted architecture baseline for MVP.

## Document responsibility

Purpose: record deployment and dependency boundaries. Owns architectural decomposition, not module implementations or numeric capacity targets. Depends on [project context](../../PROJECT_CONTEXT.md) and [overview](../architecture/overview.md). Used by P01–P24. Tested by P00 ADR/consistency review and later P01/P05 import-boundary and integration checks.

## Context

The subsystem must integrate with an existing commerce platform while enforcing seller isolation, approval, budget reservations, and execution consistency. Its initial operating model should be simple enough to deliver and support without introducing distributed ownership of the same mutation path.

## Decision

Use a Python/FastAPI modular monolith with Presentation -> Application -> Domain and Infrastructure implementations of inward-facing ports. Thin route handlers parse/authorize, call use cases, and map results. Application coordinates transactions; framework-independent Domain owns invariants. Run HTTP and Celery worker processes from the same release with shared application/domain logic and authoritative PostgreSQL persistence.

Keep Identity, Catalog, Inventory, Orders and Content Hub as existing external bounded contexts accessed through narrow adapters. A logical boundary does not require a new deployed service. Wire dependencies only at composition roots and keep concrete adapters out of Domain/Application imports.

## Alternatives

- Microservices from the outset: permit independent deployment but add distributed transactions, network failures and ownership overhead before measured need.
- An unstructured single application: easy to begin but blurs tenant/approval checks and makes later extraction or testing costly.
- A new commerce platform: duplicates existing source-of-truth capabilities and exceeds scope.

## Consequences

Local transaction boundaries simplify approval, reservation, audit and dispatch-intent consistency. Development/release coordination remains shared. HTTP and background workloads can scale separately as processes, but a shared database needs query isolation and connection-pool discipline. Enforce module boundaries by review and tests so the monolith does not become tightly coupled through concrete adapters.

## Replacement Trigger

Consider selective service extraction only when measured resource contention, independent release needs, fault isolation, or stable team ownership cannot be addressed by modular boundaries, process scaling and database tuning. Require evidence against agreed operational targets, a clear owning context and data contract, and a migration/recovery plan preserving approval/idempotency/tenant invariants. A new ADR must justify the extraction; growth expectations alone do not authorize microservices, Kafka or Kubernetes. No numeric trigger is invented in this ADR.
