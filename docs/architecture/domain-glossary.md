<!--
PURPOSE: Establish a shared, unambiguous vocabulary for the Marketing & Advertising bounded context.
RESPONSIBILITY: Defines domain terms and ownership boundaries; it does not define database schemas or API payloads.
DEPENDENCIES: The P00 architecture overview and existing Maroc Affiliate platform terminology.
USED BY: Product, engineering, QA, support, and later API/domain documentation.
TESTED BY: P00-T terminology review and P00-V acceptance validation.
-->

# Marketing & Advertising domain glossary

| Term | Definition |
| --- | --- |
| Seller | The Maroc Affiliate tenant that owns the advertising configuration, proposals, campaigns, metrics, approvals, and audit records in this bounded context. |
| Principal | The authenticated actor whose trusted identity, seller context, roles, and claims are evaluated for an operation. A principal may act only within authorized seller scope. |
| Seller scope | The tenant boundary identified by seller_id and enforced at every seller-owned query, service call, mutation, log policy, and response. |
| Meta connection | A seller-authorized relationship to Meta, represented by encrypted credential references and lifecycle metadata. The raw OAuth token is never exposed to the frontend or LLM. |
| Ad account link | The authorized association between a seller and a specific Meta ad account that may be read or mutated through the MetaAdsGateway. |
| MetaAdsGateway | The typed infrastructure boundary used by application code to read from or write to Meta. It hides MCP, API, SDK, authentication, and transport details from the domain. |
| Campaign proposal | A versioned, structured recommendation for a potential Meta campaign, built from authorized seller, product, creative, inventory, order, and policy context. It is not an external campaign. |
| Exact payload | The canonical, versioned campaign mutation payload, including a stable hash and policy-relevant fields, that a seller approves. A changed payload requires a new approval. |
| Approval | A recorded seller decision on one exact payload version within a defined scope and expiry. Approval authorizes an execution attempt only after immediate revalidation; it does not guarantee publication. |
| Financially sensitive mutation | An external action that can create spend or materially change a seller's advertising or operational exposure, including campaign creation, activation, budget change, or equivalent Meta write. It always requires the full approval and mutation safety gate. |
| Campaign execution | The internal record of one idempotent attempt to perform a Meta mutation for an approved exact payload. It tracks dispatch, ambiguity, retries, reconciliation, and final outcome. |
| Idempotency key | A stable, unique key that binds a logical external mutation to safe repeated delivery and reconciliation behavior. It prevents duplicate campaign creation after retries or timeouts. |
| Reconciliation | The controlled process that resolves an ambiguous, incomplete, or stuck external execution using authoritative persisted evidence and Meta gateway lookups. |
| Campaign | A Meta advertising object or campaign representation that has been confirmed or synchronized through the Meta gateway. Its external identifiers and status are stored tenant-scoped. |
| Creative | A seller-authorized marketing asset or asset reference selected from the existing Content Hub for use in a proposal. Content Hub remains its source of truth. |
| Product context | Authorized read-only catalog data needed to assess eligibility and formulate a proposal. Catalog remains its source of truth. |
| Inventory context | Authorized read-only stock, availability, and warehouse data used to validate campaign eligibility. It must be refreshed before a sensitive mutation. |
| Commerce outcome | A factual order or fulfillment result, such as delivered order, cancellation, return, margin, or warehouse availability, supplied by existing Maroc Affiliate services. |
| Performance snapshot | A time-bounded, sourced record of Meta advertising performance captured for analysis. It records freshness and provenance rather than replacing Meta or commerce truth. |
| Delivered-order ROAS | A commerce-aware return-on-ad-spend measure based on attributable delivered-order value divided by attributable ad spend. Its attribution window, currency, exclusions, and data freshness must be displayed with the result. |
| Recommendation | A non-authoritative, evidence-linked suggestion for campaign creation or improvement. It may be rule-based or LLM-assisted and never directly invokes a financial mutation. |
| Deterministic policy | A testable business rule that evaluates permission, ownership, budget, stock, approval, payload validity, and state transition conditions without deferring authority to an LLM. |
| Policy validation | The process of applying deterministic policies to an input or exact payload. A failed validation blocks publication and returns a safe explanation. |
| LangGraph workflow | An explicit state-machine workflow that coordinates authorized context gathering, structured LLM generation, validation, interrupt/resume for approval, and safe result handling. |
| Read tool | A constrained capability that retrieves authorized data without changing external or authoritative state. It may be invoked automatically only inside a permitted workflow. |
| Write tool | A capability that can change external or authoritative state. A model cannot invoke it directly; the application performs it only after all mutation controls pass. |
| Audit event | An immutable, tenant-scoped record of a sensitive action, decision, state transition, actor, timestamp, correlation/request identifier, and safe evidence reference. It never stores secrets. |
| Kill switch | An audited, deny-by-default administrative control that prevents new sensitive marketing mutations while preserving safe reads, status visibility, and reconciliation behavior as defined by policy. It requires the explicit marketing_admin capability and either platform scope (global) or seller scope (named tenant). |
| External ambiguity | A state in which a network timeout, malformed response, or dependency failure prevents the system from knowing whether an external mutation occurred. It requires reconciliation rather than an assumed result. |
| Trusted identity | The identity and tenant claims supplied by the existing Maroc Affiliate authentication system after validation. The marketing service consumes rather than reimplements this authority. |
