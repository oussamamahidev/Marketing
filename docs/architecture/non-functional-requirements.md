<!--
PURPOSE: Define measurable quality, security, reliability, and operational expectations for the MVP.
RESPONSIBILITY: States cross-cutting requirements and operational evidence; it does not implement controls or replace product policies.
DEPENDENCIES: P00 architecture overview, existing identity/privacy policies, and later platform contracts.
USED BY: P01-P24 engineering, security review, test planning, deployment, and runbooks.
TESTED BY: P00-T documentation review, P00-V acceptance validation, and later security/integration/operational tests.
-->

# Non-functional requirements

## Scope of these targets

These are initial MVP targets and acceptance expectations. Numeric service-level objectives must be validated against real traffic, Meta limits, and platform policy before they become contractual external SLAs. A slower external provider never permits a safety control to be skipped.

## Binding numeric decisions

`BUSINESS_CONSTANTS.md` is the binding source for currencies, thresholds, limits,
cadences, and recovery objectives. This document deliberately does not invent or
duplicate those values. A value marked `<<SET>>` remains a product-owner decision:
later configuration startup must fail with a clear configuration error when it is
required but unresolved, and P05 must not implement a deterministic policy that
depends on it. Those unresolved P05 decisions do not block P00-P04 unless a specific
prompt depends on the affected constant.

## Security and tenant isolation

- Every seller-owned read and write is authorized and constrained by seller_id at the query or service boundary. A client-provided identifier alone is never sufficient.
- The application applies RBAC, ownership checks, and selected ABAC rules before a use case loads or changes seller data.
- Administrative operations are denied unless the principal has the explicit marketing_admin capability and a verified platform or seller scope. They are audited. This administrative authority does not bypass deterministic policy, exact-payload seller approval, or tenant isolation.
- Meta OAuth tokens, refresh tokens, encryption keys, authorization headers, and credential references are encrypted/protected in infrastructure and are excluded from frontend responses, logs, errors, and LLM context.
- Least privilege applies to service credentials, database roles, Meta permissions, worker queues, and administrative actions.
- Seller input, creative metadata, external API responses, URLs, and LLM output are untrusted. Prompt-injection defenses include context delimiting, typed allow-listed inputs/tools, output-schema validation, and refusal to treat instructions embedded in data as authority.
- Financially sensitive writes fail closed if authoritative persistence, authorization, policy validation, approval verification, or pre-mutation revalidation is unavailable.
- Rate limits, CORS/CSRF policy, secure headers, SSRF controls, dependency scanning, and secret-management hardening are implemented in the dedicated security phase without weakening the rules above.

## Reliability, consistency, and recovery

| Requirement | MVP expectation |
| --- | --- |
| Authoritative state | PostgreSQL is the source of truth for proposals, approvals, executions, audit events, and reconciliation state. Redis loss must not change a final business decision. |
| Sensitive mutation durability | Persist the approved exact payload, idempotency key, intent, and audit evidence before dispatch. Do not dispatch when the required transaction cannot commit. |
| Transaction scope | Do not hold a database transaction open while awaiting an LLM, Meta, or other external dependency. Persist safe state transitions around the side effect instead. |
| Idempotency | A duplicate request for the same logical action must resolve to its existing execution or a safe conflict, never create an untracked duplicate external mutation. |
| Ambiguous outcome | Timeouts, connection resets, malformed dependency responses, and worker crashes result in PendingConfirmation/Reconciliation, not an invented success or failure. |
| Retry behavior | Retries are bounded, classified, observable, and reuse the correct idempotency semantics. Unsafe or final failures require review rather than blind retry. |
| Concurrency | Policy-relevant state is checked immediately before mutation. Concurrent edits that invalidate an approval produce a conflict or supersede the stale proposal. |
| Recovery | Stuck executions are discoverable and reconciled by workers. Backup/restore procedures and recovery objectives are completed before production handoff. |

## Initial performance and capacity targets

- Authorized, database-backed read endpoints should target p95 application processing of 500 ms or less when dependencies are healthy; external and LLM latency is measured separately.
- A route must not hold a client connection while performing an unbounded synchronization or reconciliation task. Long-running work is delegated to Celery and exposes a durable status.
- Proposal generation and Meta writes have explicit application timeouts, dependency timeouts, and status transitions; a timeout must preserve enough state for retry or reconciliation.
- Tenant isolation and correctness take priority over throughput. Capacity changes must not introduce unscoped bulk reads or high-cardinality metric labels.
- Performance snapshots must capture their source time and retrieval time so analysis can communicate freshness rather than imply real-time certainty.
- The intended pre-production control target is 100% of financially sensitive mutation attempts carrying a durable audit event, idempotency reference, and policy/approval outcome. Any gap blocks release until explained and remediated.

## Availability and graceful degradation

- When Meta, a read-only internal dependency, Redis, or the LLM is unavailable, the system returns a safe, canonical error or defers work; it does not fabricate data.
- Existing approved campaigns remain visible when a non-authoritative cache is unavailable, provided PostgreSQL is available.
- New financially sensitive mutations are unavailable when a required authoritative dependency is unavailable.
- Health endpoints distinguish process liveness from readiness to serve work safely. Readiness must include the dependencies necessary for the role being served.

## Error contract

Every application error response uses a stable machine-readable **code** and a **request_id** safe for support. A correlation_id may supplement tracing but never replaces request_id. The response may include only a safe human-readable message and allow-listed field details; it must not include raw upstream payloads, stack traces, credentials, or tokens.

P02 implements this canonical contract. P00 freezes these intended codes and categories:

| Condition | Code | HTTP category | Required behavior |
| --- | --- | --- | --- |
| Invalid request shape | invalid_request | 400 | Explain the safe request failure without leaking data. |
| Deterministic validation failure | validation_error | 422 | Explain the safe field/rule failure without leaking data. |
| Missing or invalid authentication | unauthenticated | 401 | Do not disclose tenant/resource existence. |
| Authenticated but unauthorized | forbidden | 403 | Do not disclose protected resource details. |
| Resource not found within the active tenant | resource_not_found | 404 | Treat cross-seller references as not found unless policy requires a stronger response. |
| Duplicate request, stale version, invalid transition, or idempotency conflict | state_conflict | 409 | Return the safe current/status reference where permitted. |
| External outcome requires reconciliation | external_outcome_ambiguous | 409 | Do not claim success or failure; return only a safe execution/status reference. |
| Rate limit | rate_limited | 429 | Include retry guidance where safe. |
| Upstream/dependency failure | upstream_bad_gateway | 502 | Use a canonical error, request_id, and safe retry/status guidance; never return raw payloads or credentials. |
| Required upstream dependency unavailable | upstream_unavailable | 503 | Use a canonical error, request_id, and safe retry/status guidance; never return raw payloads or credentials. |
| Upstream timeout | upstream_timeout | 504 | Use a canonical error, request_id, and safe retry/status guidance; never return raw payloads or credentials. |

## Logging, tracing, and metrics

Observability uses structured logs, OpenTelemetry-compatible traces, error tracking,
and low-cardinality metrics suitable for Prometheus/Grafana.

### Logging

- Emit structured logs for lifecycle and dependency-failure events with request_id and correlation_id.
- Include safe seller/campaign/execution references only according to the project privacy policy. Do not log raw customer PII unless operationally required and approved.
- Never log authorization headers, OAuth tokens, encryption keys, raw external payloads containing secrets, or entire LLM prompts when they may contain sensitive data.
- Log security-relevant denials, state transitions, approval decisions, dispatch attempts, ambiguity detection, and reconciliation outcomes with an appropriate severity.

### Tracing

- Propagate request/correlation identifiers across HTTP, application use cases, Celery jobs, internal adapters, Meta gateway calls, and LLM calls.
- Use OpenTelemetry-compatible traces to show the path of a proposal or execution without attaching secrets or uncontrolled seller text.

### Minimum metrics

Metrics use low-cardinality labels such as operation, dependency, outcome class, and safe state; do not label by seller_id, campaign ID, raw error message, or prompt text.

- Counters: Meta gateway calls and outcomes; proposal validation outcomes; approval outcomes; execution/reconciliation outcomes; dependency failures.
- Histograms: latency for Meta, internal adapter, LLM, proposal-generation, publish, and reconciliation operations.
- Gauges: queued/stuck executions and snapshot freshness where a bounded aggregation is available.
- Alerts: rising sensitive-mutation failures, unresolved ambiguity beyond its policy window, repeated policy denial anomalies, dependency error rates, and stale synchronization.

## AI quality and safety

- LLM providers are reached through an abstraction that requests strict structured output. Schema failures are handled as untrusted invalid output.
- The graph permits only explicitly registered, least-privilege read tools. It never gives an LLM raw credentials or a direct write capability.
- Generated proposals retain their evidence references and limitations so deterministic validation and seller review can assess them.
- AI evaluation covers schema conformance, unsupported claims, tenant leakage, prompt-injection resistance, unsafe mutation suggestions, and safe refusal behavior.
- A recommendation may explain trade-offs but cannot overrule stock, budget, permissions, approval, or a deterministic policy.

## Operational assumptions and risks

| Assumption or risk | Consequence | Required mitigation |
| --- | --- | --- |
| Existing identity can provide a validated principal and seller scope. | Incorrect or absent tenant claims would risk isolation. | Define and test the trusted identity contract before enabling seller endpoints. |
| Catalog, inventory, orders, and Content Hub offer typed read contracts or can be adapted safely. | Missing or stale data may block a proposal or make analysis incomplete. | Make freshness explicit, validate inputs, and fail closed when required mutation context is unavailable. |
| Meta rate limits, permissions, token expiration, and API behavior may vary. | Publishing or sync may fail or be ambiguous. | Classify gateway errors, refresh/reconnect safely, use idempotency, and reconcile. |
| Attribution from ad performance to delivered commerce outcomes is imperfect. | ROAS and recommendation confidence may be misleading. | Document attribution logic, freshness, exclusions, and confidence/limitations with every analysis. |
| LLM output can be incorrect, maliciously influenced, or unavailable. | Unsafe or low-quality suggestions are possible. | Use sanitized typed context, strict schemas, deterministic policy, human approval, evaluation, and graceful degradation. |
| Background jobs can be delayed or duplicated. | Snapshots or reconciliations may lag. | Persist job-relevant state, use idempotency, monitor freshness, and bound retries. |
| Traffic or analytical retention may grow beyond transactional capacity. | Seller analytics can become slow or costly. | Measure query load and use the documented PostgreSQL-to-analytical-storage replacement trigger. |

## Meta launch dependencies

The following external processes can block launch even when engineering work is
complete. The product owner should start them early and run them in parallel with
engineering, beginning in P00 rather than waiting for the Meta-connection phase.

| Launch risk | Why it matters | Required action |
| --- | --- | --- |
| Meta Business verification | An unverified business can prevent production advertising access. | Start verification early and track its status as a launch dependency. |
| Meta App Review and required permissions | Production use may require App Review for `ads_management` and `ads_read`. | Submit the required permissions early and retain the review evidence. |
| Meta advertising policy compliance | Generated ad copy, creatives, and targeting must comply with Meta advertising policies. | Include policy review in product and creative readiness; block non-compliant publication. |
| Review or resubmission delay | A review can require clarification, changes, or resubmission. | Plan schedule contingency and continue engineering work in parallel. |

## Edge-case expectations

| Edge case | Expected safe behavior |
| --- | --- |
| Missing resource or cross-seller reference | Return a tenant-safe not-found/forbidden response without revealing another seller's data. |
| Stale proposal or approval | Reject or supersede it; require a fresh exact payload and approval. |
| Duplicate publish request | Resolve via idempotency to the existing execution or return a safe conflict. |
| Timeout during Meta mutation | Mark the outcome ambiguous, persist evidence, and reconcile before retrying. |
| Required dependency unavailable | Defer safe read/work where possible; block a sensitive mutation when required authoritative context cannot be confirmed. |
| Malformed dependency response | Treat as an upstream failure; do not map unknown fields into an approved payload. |
| Expired credentials, including expired Meta credentials | Prevent write dispatch, report a safe reconnect-needed state, and audit the event. |
| Concurrent update to policy-relevant input | Detect the version/state conflict and invalidate approval before mutation. |
| Partial failure across persistence and Meta | Preserve durable intent/audit state and reconcile; do not claim completion from a partial result. |
| Cancellation or retry request | Permit only transitions that do not hide an already dispatched or ambiguous external outcome. |

## Evolution thresholds

The system remains a modular monolith with PostgreSQL and Celery until the evidence-based triggers in the architecture overview and ADRs are met. Any move to Temporal, selective services, or specialized analytical storage requires a new ADR covering data ownership, migration, security, observability, rollback, and failure semantics.
