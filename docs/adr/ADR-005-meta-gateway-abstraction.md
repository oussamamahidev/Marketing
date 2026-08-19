<!--
PURPOSE: Record the integration boundary that isolates Meta-specific mechanics.
RESPONSIBILITY: Governs the MetaAdsGateway contract; it does not own authorization or deterministic business policy.
DEPENDENCIES: Application use cases, domain contracts, and Meta infrastructure adapters.
USED BY: Meta connection, read, mutation, sync, and reconciliation implementation.
TESTED BY: P00-T ADR review and later gateway contract/integration tests.
-->

# ADR-005: Hide Meta API/MCP details behind MetaAdsGateway

**Status:** Accepted — P00 architecture baseline

## Context

Meta APIs, SDKs, MCP adapters, OAuth mechanics, provider payload shapes, error models, rate limits, and reconciliation behavior are external concerns. Allowing those details into routes, domain policies, or AI workflows would bind business logic to transport choices and create pathways for raw credentials or unsafe payloads to leak.

## Decision

Define a narrow typed MetaAdsGateway port consumed by application use cases. Infrastructure supplies the MCP/API adapter or adapters. The gateway:

- exposes only required read and write capabilities;
- maps provider payloads and errors to canonical typed results;
- owns provider protocol, credential use, idempotency submission details, and external ambiguity classification;
- supports safe reconciliation lookups; and
- does not decide seller authorization, budget/stock policy, or whether a mutation is approved.

Read capabilities are implemented before write capabilities. A model never receives a generic MCP tool or direct provider credential.

## Alternatives considered

| Alternative | Why it was not selected for the MVP |
| --- | --- |
| Direct Meta SDK/MCP calls from routes or use cases | Leaks provider concerns through the application and makes testing, error handling, and credential control inconsistent. |
| Generic MCP tools exposed to the LLM | Creates an unsafe path from untrusted model output to external mutation. |
| Domain model based on raw Meta payloads | Couples business invariants to an unstable external representation and risks unsafe response exposure. |

## Consequences

- Application/domain logic is testable with gateway fakes and insulated from provider changes.
- Adapter mapping, contract tests, credential protection, and canonical error translation become explicit responsibilities.
- Idempotency and reconciliation semantics are visible at the integration boundary rather than hidden in routes or workers.
- Introducing another channel later requires a deliberate boundary review, not a generic abstraction created prematurely.

## Replacement trigger

Replace an adapter when the underlying Meta API/MCP capability is deprecated, incompatible, or unable to meet the gateway contract safely. Split or expand the port only when concrete multi-channel requirements make it leaky.

Extract an integration service only with evidence of independent release, scaling, or credential-isolation needs and a new ADR that preserves tenant scope, auditability, idempotency, canonical errors, and reconciliation behavior.
