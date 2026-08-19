<!--
PURPOSE: Freeze the MVP scope, boundaries, control flows, and architectural constraints.
RESPONSIBILITY: Defines the Marketing & Advertising bounded context; it does not prescribe implementation details for later phases.
DEPENDENCIES: Product requirements and the existing Maroc Affiliate platform contracts.
USED BY: P01-P24 implementation, testing, validation, and operations work.
TESTED BY: P00-T documentation review and P00-V acceptance validation.
-->

# Maroc Affiliate AI Marketing Assistant architecture overview

## Status and intent

This document is the P00 architecture baseline. It defines the minimum safe, production-oriented MVP for an AI-assisted Meta advertising capability embedded in Maroc Affiliate. Later work may refine implementation details, but it must preserve the scope, boundaries, and safety invariants recorded here unless a superseding ADR is accepted.

The system helps a seller create, approve, publish, observe, and improve Meta campaigns using Maroc Affiliate commerce data. It is an assistant, not an autonomous advertising buyer.

## Scope

### Bounded context: Marketing & Advertising

The Marketing & Advertising bounded context owns:

- Meta connection references and ad-account links for a seller.
- Campaign proposals, exact payload versions, approvals, executions, reconciliation records, campaign status, performance snapshots, recommendations, and marketing audit events.
- Policy evaluation that decides whether a proposed advertising action may proceed.
- Orchestration of AI-assisted proposal generation and campaign analysis.
- Adaptation of Meta Ads, LLM, and read-only Maroc Affiliate platform data behind narrow interfaces.

It does not own:

- Authentication, user identity, product truth, inventory truth, order truth, warehouse operations, customer records, or Content Hub assets.
- The seller's Meta account or Meta's final campaign state.
- A general-purpose knowledge base, RAG system, vector database, data lake, or cross-channel marketing platform in the MVP.

### Actors

| Actor | Responsibility |
| --- | --- |
| Seller | Connects an authorized Meta account, selects eligible inputs, reviews proposals, approves exact campaign payloads, and views outcomes. |
| Principal | The authenticated identity acting for a seller; its permissions and tenant scope are verified before every seller-owned operation. |
| Platform administrator | Performs support and safety operations only with an explicit marketing_admin capability and an explicit permitted scope. Administrative access is deny-by-default and does not bypass tenant protections, policy validation, or seller approval. |
| Existing Maroc Affiliate services | Provide trusted identity and read-only product, inventory, order, warehouse, and creative context through explicit contracts. |
| Meta Ads | External advertising platform; its API or MCP implementation remains behind the Meta gateway. |
| LLM provider | Produces constrained, structured suggestions and analysis only; it has no authority to mutate state or decide policy. |
| Worker runtime | Performs scheduled synchronization, retries, and reconciliation under the same authorization, audit, and safety rules as HTTP-triggered work. |

### Primary use cases

1. A seller connects and manages a Meta connection and permitted ad-account link.
2. A seller selects a Maroc Affiliate product and an existing Content Hub creative.
3. The system gathers authorized, tenant-scoped commerce context and generates a structured campaign proposal.
4. Deterministic policies validate the proposal against permissions, budget, stock, eligibility, and business rules.
5. The seller approves one exact, versioned payload before an external financial mutation.
6. The system publishes idempotently through the Meta gateway, records the result, and reconciles ambiguous outcomes.
7. Background work synchronizes Meta performance and joins it to commerce outcomes such as delivered orders, cancellations, returns, margin, stock, and warehouse availability.
8. The seller receives evidence-based campaign diagnosis, recommendations, and constrained assistant responses.

## Canonical requirements

### MUST

- Enforce seller isolation at every seller-owned lookup and mutation using seller_id at the query or service boundary.
- Treat PostgreSQL as the authoritative source of truth. Redis may support caching, locks, queues, and ephemeral coordination only.
- Keep route handlers thin: parse and authorize, invoke an application use case, then map its result.
- Keep business invariants framework-independent in the domain layer.
- Use narrow, typed repository and gateway interfaces. Translate integration errors into canonical application errors.
- Treat every LLM result and all seller/external text as untrusted input.
- Require authorization, deterministic policy validation, exact-payload human approval, idempotency, audit, and immediate pre-mutation revalidation for financially sensitive external writes.
- Fail closed when authoritative persistence is unavailable for a critical mutation.
- Make external writes reconcilable; a timeout or malformed response must be represented as ambiguity, not guessed as success or failure.
- Keep OAuth tokens, credentials, encryption keys, and other secrets outside LLM prompts and frontend responses.
- Record immutable, tenant-scoped audit events for sensitive decisions and state transitions.

### SHOULD

- Provide clear seller-facing explanations for blocked proposals and recommendations, with the evidence and limitations that support them.
- Prefer asynchronous processing for slow external calls and performance synchronization while retaining visible status.
- Be observable through structured logs, tracing, low-cardinality metrics, and error tracking.
- Be deployable initially as Dockerized application and worker processes with managed PostgreSQL and Redis.
- Make state transitions, retry eligibility, and cancellation behavior explicit and testable.

### NICE TO HAVE

- Seller-configurable but policy-bounded recommendation preferences.
- Explainable profitability views segmented by product, campaign, and time range.
- Event/conversion integration for fulfilled commerce outcomes after the MVP.
- Recommendation-first automation rules only after the MVP safety model has proven reliable.

### Out of scope for the MVP

- Autonomous campaign publishing or budget changes based only on an LLM recommendation.
- Kafka, Kubernetes, microservices, Temporal, a vector database, RAG, and a data lake.
- Additional advertising channels beyond Meta.
- Replacing the existing identity, catalog, inventory, orders, warehouse, or Content Hub systems.
- Treating Redis, Meta, or an LLM provider as the source of truth for seller authorization or campaign approval.

## Architecture and dependencies

The service starts as a Python/FastAPI modular monolith:

~~~text
HTTP request or worker
        |
        v
Application use case
        |
        v
Domain policies and state transitions
        |
        v
Repository or gateway interface
        |
        v
PostgreSQL / Redis / Meta / LLM / internal Maroc Affiliate adapters
~~~

The permitted dependency direction is:

~~~text
Presentation -> Application -> Domain <- Infrastructure
~~~

- Presentation contains FastAPI endpoints, request parsing, authentication dependencies, and result mapping. It never implements policy or performs a direct integration call.
- Application coordinates use cases, transaction boundaries, authorization checks, orchestration, and calls into domain policies and ports.
- Domain contains entities, value objects, state machines, deterministic policies, and repository/gateway contracts. It is independent of FastAPI, SQLAlchemy, Celery, LangGraph, Meta, and LLM SDKs.
- Infrastructure implements the domain/application contracts for PostgreSQL, Redis, cryptography, Meta, LLM providers, and existing internal services.

### Integration boundaries

| Boundary | Direction and contract | Non-negotiable rule |
| --- | --- | --- |
| Identity | The service consumes a trusted authenticated principal and seller context. | Authentication is not reimplemented; application code enforces RBAC, ownership, and selected ABAC policies. |
| Catalog | Read-only typed product eligibility, pricing, and product data. | Every request is seller-scoped or otherwise explicitly authorized. |
| Inventory and warehouse | Read-only stock, availability, and fulfillment context. | Fresh availability is rechecked immediately before an external mutation. |
| Orders | Read-only delivered, cancelled, returned, and margin-related outcomes. | Commerce outcomes are joined by stable identifiers and documented attribution rules. |
| Content Hub | Read-only creative metadata and authorized asset references. | The service never exposes cross-seller creatives or sends unsafe asset/credential data to an LLM. |
| Meta Ads | MetaAdsGateway exposes typed read and write capabilities. | MCP/API/SDK details do not escape infrastructure; all writes are idempotent and auditable. |
| LLM provider | Provider adapter accepts sanitized authorized context and returns a strict schema. | Output is advisory and must pass deterministic validation before any state-sensitive use. |

### Planned typed ports

P00 freezes the following narrow port responsibilities before any concrete adapter is implemented. The names describe contracts, not database models or vendor payloads. Every seller-owned operation receives trusted seller_id from the application layer; a caller-supplied tenant identifier cannot override it.

| Port | Minimum responsibility | Typed result / error boundary |
| --- | --- | --- |
| CatalogReader | Load one seller-authorized product and its eligibility/pricing context. | ProductContext or canonical tenant-safe not-found/upstream error. |
| InventoryReader | Load current stock, availability, and warehouse context for a selected product. | InventoryContext with source freshness, or canonical error. |
| OrdersReader | Load bounded commerce outcomes needed for profitability analysis. | CommerceOutcomeSummary with attribution/freshness metadata, or canonical error. |
| ContentHubReader | Load one seller-authorized creative reference and metadata. | CreativeContext or canonical tenant-safe not-found/upstream error. |
| MetaAdsGateway | Manage connection/account reads, campaign reads, idempotent approved mutations, and reconciliation lookups. | Canonical Meta result, provider-neutral external reference, or explicit ambiguity/error. |
| StructuredLlmProvider | Generate a strict-schema proposal or analysis from sanitized authorized context. | Schema-validated suggestion or untrusted-output/provider error; never a mutation result. |
| Proposal, Approval, Execution, Snapshot, and Audit repositories | Persist and load authoritative tenant-scoped workflow state. | Domain records with optimistic/versioned transition support, or canonical persistence error. |

Ports must not expose raw OAuth tokens, unbounded seller data, generic provider tools, or raw external payloads. Application use cases translate their typed outcomes into canonical errors and domain policy inputs.

## Control and data flows

### Standard request or worker flow

All implementation work preserves this default:

~~~text
HTTP/Worker -> Application Use Case -> Domain Policies -> Repository/Gateway -> External/DB
~~~

The application layer resolves the principal and seller scope before loading seller-owned resources. Repositories and gateways receive the tenant context needed to prevent unscoped access. External responses are parsed into typed results; unsafe raw payloads and credentials do not cross into presentation responses or LLM context.

### AI-assisted proposal flow

~~~text
Authorized Context
  -> LangGraph state machine
  -> LLM structured output
  -> deterministic validation
  -> exact-payload human approval (when sensitive)
  -> application mutation
~~~

LangGraph coordinates explicit nodes and transitions, not an autonomous agent swarm. Read-only tools can run only with authorized, sanitized context. A write-capable tool cannot be invoked directly by a model: the application must create an approved, idempotent execution and then invoke the Meta gateway.

### Performance and profitability flow

Scheduled workers retrieve permitted Meta performance data, store immutable or versioned snapshots, and join it with authorized commerce facts. Seller-facing analysis must distinguish observed facts, calculated measures, data freshness, attribution assumptions, and LLM-generated interpretation.

## Campaign lifecycle and safety states

Proposal and execution are separate state machines so an approval of a draft cannot be confused with the outcome of an external write.

### Proposal state

| State | Meaning | Allowed next states |
| --- | --- | --- |
| Draft | Seller selections are incomplete or editable. | Generating, Cancelled |
| Generating | Authorized context is being assembled and processed by the controlled graph. | ReadyForValidation, Blocked, Failed |
| ReadyForValidation | A structured proposal exists but has not passed all deterministic checks. | PendingApproval, Blocked, Superseded |
| PendingApproval | Policies passed and one exact payload version/hash is waiting for a seller decision. | Approved, Rejected, Expired, Superseded |
| Approved | The seller approved the exact unexpired payload; it may create a linked execution after immediate revalidation. | Expired, Superseded; may create an ExecutionRequested execution |
| Blocked | A deterministic policy or input rule prevents publication. | Draft, Generating, Superseded |
| Rejected | The seller declined the exact payload. | Draft, Superseded |
| Expired | Approval or source context is no longer valid. | Draft, Superseded |
| Superseded | A later proposal or payload version replaces this one. | Terminal |
| Cancelled | The seller ended an unfinished proposal. | Terminal |
| Failed | Generation failed before a valid proposal was formed. | Draft, Generating, Cancelled |

Any payload, creative, product, budget, targeting, permissions, stock, or policy-relevant context change invalidates approval and requires a new exact payload version. State changes are audited.

### Execution state

| State | Meaning | Allowed next states | Required behavior |
| --- | --- | --- | --- |
| NotRequested | No publish action exists. | ExecutionRequested, Cancelled | Only a still-valid Approved proposal may create ExecutionRequested; no external write is allowed before then. |
| ExecutionRequested | An approved payload and idempotency key were recorded. | Dispatching, Cancelled, FinalFailure | Revalidate authority and policy before dispatch. Cancellation is allowed only while no dispatch attempt has begun. |
| Dispatching | The Meta gateway call is in progress. | Succeeded, PendingConfirmation, RetryableFailure, FinalFailure | Persist attempt metadata without logging secrets. A possibly delivered request becomes PendingConfirmation, never Cancelled. |
| PendingConfirmation | A timeout or ambiguous external outcome prevents a reliable result. | Reconciliation | Reconcile using the idempotency key/external identifiers; do not repeat blindly. |
| Succeeded | Meta confirmed the external mutation. | None (terminal) | Persist external identifiers and an audit event. |
| RetryableFailure | The failure is classified as safely retryable and no ambiguous external delivery remains. | ExecutionRequested, FinalFailure, Cancelled | A retry re-enters ExecutionRequested with the same logical idempotency key; cancellation is allowed only when dispatch was proven not to occur. |
| FinalFailure | The action cannot safely continue automatically. | None (terminal) | Surface the outcome and retain evidence for support. |
| Reconciliation | A worker is resolving an ambiguous or stuck execution. | Succeeded, RetryableFailure, FinalFailure, PendingConfirmation | Transition only with authoritative evidence. PendingConfirmation remains valid when evidence is still inconclusive. |
| Cancelled | A not-yet-dispatched execution was cancelled. | None (terminal) | Never claim that an already dispatched or ambiguous external mutation was cancelled. |

No execution transition outside this table is valid; it must be rejected as a state conflict. A new execution cannot be created from a proposal that is no longer Approved, and a retry cannot use a new idempotency key for the same logical external mutation.

## Safety invariants

1. An LLM recommendation is never an authority for permissions, budget, stock, approval, or external mutation.
2. Seller A cannot access Seller B data, credentials, creatives, campaigns, metrics, approvals, or audit events.
3. Read actions can be automatic only after authorization; write actions require all required controls.
4. Exact-payload approval binds the seller decision to a version/hash, scope, and expiry. It is not a blanket approval.
5. Critical financial mutations fail closed without authoritative persistence.
6. Every external write has an idempotency strategy, audit trail, and reconciliation path.
7. Stock, permissions, budget limits, approval status, and seller scope are revalidated immediately before mutation.
8. Secrets never enter LLM prompts, logs, frontend responses, or raw error messages.

### Administrative safety controls

Administrative controls are exceptional safety actions, not a second path around seller authorization. Every administrative operation requires the explicit marketing_admin capability and a server-verified scope:

- A **platform** scope may activate a global kill switch that blocks new financially sensitive mutations for every seller.
- A **seller** scope may activate a tenant-scoped kill switch only for the named seller and must not grant access to another seller's data.
- Both forms are deny-by-default, immutable-audit-event producing, and preserve safe status reads and reconciliation as policy permits.
- No ordinary administrative capability may approve a seller's mutable campaign payload, bypass deterministic policy, or suppress required audit evidence.

## Evolution triggers

The MVP deliberately avoids premature distributed architecture. A future ADR is required before changing these boundaries.

| Current choice | Reconsider only when evidence shows | Likely next step |
| --- | --- | --- |
| Celery + Redis jobs | Long-running financial workflows need durable timers, resume-after-human-approval, compensation, or exactly-once workflow history beyond Celery's safe retry model. | Evaluate Temporal for those workflows only. |
| Modular monolith | A bounded capability has independent deployment/scaling, stable contracts, a distinct ownership boundary, and measurable monolith friction that cannot be solved internally. | Extract one selective service with an explicit data-ownership plan. |
| PostgreSQL performance analytics | Retention, query concurrency, aggregation latency, or cost makes timely seller analytics impractical while transactional data remains protected. | Add specialized analytical storage with governed, reproducible ingestion. |

## Delivery guardrails

P00 establishes documentation only. P01-P24 proceed in dependency order and each implementation prompt must pass its corresponding testing and validation prompts before its dependent work begins. P25-P28 remain optional future work and do not redefine the MVP baseline.
