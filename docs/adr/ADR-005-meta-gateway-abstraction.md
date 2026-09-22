# ADR-005: Hide Meta and MCP transport details behind MetaAdsGateway

Status: Accepted architecture baseline for MVP.

## Document responsibility

Purpose: define the external advertising integration boundary. Owns port/adapter responsibilities, not concrete API endpoints, credentials or provider guarantees. Depends on [project context](../../PROJECT_CONTEXT.md), [overview](../architecture/overview.md), and [approval ADR](ADR-006-human-approval.md). Used by P07/P08/P12–P17 and optional P28. Tested by P00 review and later adapter contracts, auth isolation, timeout/partial-write and reconciliation tests.

## Context

Meta may be accessed through MCP or a direct API adapter. Domain policies should not depend on transport tool names, provider payloads, OAuth mechanics or SDK exceptions. Both transports can fail after a side effect is applied.

## Decision

Define MetaAdsGateway as a narrow typed application port. Infrastructure implements MCP/API translation, credential resolution, request validation, response parsing and safe error classification. Domain/Application pass seller/account references and explicit action/query types; they do not construct raw provider calls.

Introduce authorized read capabilities first in P08. P12 adds write methods accessible only from approved application mutation use cases. AI tools receive a separately exposed read-only capability surface; gateway existence is not permission for the model to call all methods.

The mutation contract accepts a canonical approved payload and durable operation identity, and returns known success, known rejection or unknown outcome. Preserve remote object/step IDs, account scope and safe provider correlation evidence for reconciliation. Provider-specific fields remain inside typed integration DTOs; raw unsafe payloads never enter domain errors or user responses.

Verify currency, account access, actual provider idempotency behavior, read-after-write/reconciliation capabilities and multi-object publication semantics in P08/P12. Never assume a local idempotency key is natively enforced by Meta. Account credentials are decrypted only inside Infrastructure and are tenant-bound. Auth scope or connection revocation blocks use even if a cached token is available.

## Alternatives

- Call Meta/MCP directly from routes or LangGraph tools: couples transport to business logic and creates alternate mutation paths.
- Embed a Meta SDK in Domain: makes invariants provider-dependent and difficult to test without SDK fixtures.
- Build a universal multi-channel ad platform now: widens semantics before a second provider is in scope.

## Consequences

Policies and use cases can be tested with typed fakes; adapter contract tests still need verified provider fixtures/sandbox evidence. Transport changes stay mostly inside Infrastructure. Explicit ambiguity adds application state and reconciliation work, but avoids unsafe retries. Meta-specific concepts can remain in this Meta-focused port; optional multi-channel support should not prematurely flatten important provider behavior.

## Replacement Trigger

Replace or switch the MCP/API adapter when verified permission, feature, security, rate-limit or reliability requirements cannot be met by the current adapter. Preserve and rerun gateway contract/safety tests, reconcile in-flight operations and retain historical IDs. Generalize the port only for an approved second-channel requirement under optional P28 with equivalent safety semantics; no MVP multi-provider framework is required.
