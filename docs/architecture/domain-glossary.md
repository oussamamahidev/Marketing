# Domain glossary

## Document responsibility

This document owns canonical Marketing & Advertising terminology, not implementation types or numeric policy. It depends on [PROJECT_CONTEXT.md](../../PROJECT_CONTEXT.md), [BUSINESS_CONSTANTS.md](../../BUSINESS_CONSTANTS.md), and the lifecycle contracts in [overview](overview.md). All implementation, API, UI, and evaluation phases use these terms. P00 terminology/consistency review checks this document; later domain, contract, and API tests check their implementation.

| Term | Canonical meaning and boundary |
|---|---|
| Marketing & Advertising | Bounded context that owns local campaign planning, approval, execution, measurement, and recommendations; consumes commerce/identity facts through ports |
| Seller | Maroc Affiliate tenant that owns advertising resources; identified by `seller_id`, not by a user ID or Meta account ID |
| Principal | Verified human or service identity with permissions and seller memberships; a principal may have access to more than one seller, but each operation has one explicit active seller scope |
| SellerContext | Trusted active seller identity and authorization context derived from verified membership; never accepted as authority merely because the client supplied `seller_id` |
| Meta connection | Seller-scoped lifecycle record for a Meta authorization grant, its safe metadata, permissions, expiry/revocation status, and encrypted credential reference |
| Credential reference | Opaque reference to protected credentials resolved only inside trusted Infrastructure; not an OAuth token and not useful as independent authorization |
| Ad account link | Seller-owned association between a connection and a Meta advertising account, including currency and verified current access; separate from both the principal and connection |
| Product context | Typed, sourced read model combining Catalog and Inventory facts needed to evaluate a specific product; cannot replace the owning commerce systems |
| Creative | Existing Content Hub asset/version with authorized usage metadata; ownership and continued availability must be checked |
| Proposal / campaign draft | Versioned seller-owned intended campaign payload, created manually or from AI structured output; has no authority to spend |
| Canonical payload | Versioned deterministic representation of the complete effective external action; its stored content and digest bind validation, approval, and execution |
| Validation | Deterministic evaluation of permissions, eligibility, stock, budgets, currency, state, and other policy against authoritative facts; an LLM explanation is not validation |
| Approval | Durable, expiring human authorization for one exact seller/account/action/payload revision; requires revalidation at dispatch and cannot authorize changed content |
| Campaign | Local aggregate/projection associated with known remote Meta objects; contains desired state and separately observed state/freshness |
| Execution | Durable record of one approved mutation intent, its idempotency identity, dispatch steps, remote identifiers, attempts, and known or unknown outcome |
| Idempotency | Repeated submission of the same scoped key and payload resolves to the same operation; does not imply that an external provider automatically deduplicates writes |
| Reconciliation | Read-based investigation that establishes what happened remotely after an uncertain or partial execution; precedes any retry with ambiguous effects |
| Unknown outcome | External mutation may have applied but its result cannot be proven; represented by `RECONCILIATION_REQUIRED`, never by invented success/failure |
| Budget reservation | PostgreSQL-backed claim on seller budget by approved/in-flight work, retained for unresolved outcomes to prevent concurrent overspend |
| Recommendation | Evidence-backed suggestion to a seller; never an approval or executable mutation authority |
| Snapshot | Immutable/versioned observation of provider performance or commerce facts for a scoped time interval, with source, currency, observed time, and completeness metadata |
| Delivered order | Order for which authoritative commerce facts record successful delivery; current status alone must not erase delivery history after a later return |
| Cancellation | Commerce order cancellation/confirmation failure; does not contribute delivered revenue. Counts use a defined source cohort |
| Return | Returned/refunded or refused-on-delivery outcome. A refusal counts toward return-risk metrics but must not subtract revenue that was never recognized |
| Delivered-order ROAS | Net delivered revenue divided by ad spend, as defined in BUSINESS_CONSTANTS and [profitability](profitability.md); based on commerce outcomes, not Meta conversion counts |
| Contribution | Net delivered revenue less ad spend, delivered-order delivery cost, and COGS; authoritative monetary profitability measure alongside delivered-order ROAS |
| Breakeven delivered ROAS | Computed product/cohort-specific ROAS needed to cover costs; absent when a finite positive break-even point cannot be established |
| Meta-reported conversions | Provider-reported advertising measurement; always labelled “Meta-reported — informational only” and never substituted for verified delivered orders |
| Audit event | Append-only durable record of actor, tenant, action, resource/version, correlation and outcome with safe payload references; not a mutable business log or a place to store secrets |
| Kill switch | Administrative control preventing subsequent external mutation dispatch; does not itself pause already-running remote campaigns |
| Policy version | Identifier for the deterministic rule/configuration set used in validation; records historical evidence without overriding current dispatch-time checks |
| Financially sensitive action | Publication, activation/resume, pause, budget/schedule changes, and other external advertising mutations affecting spend or delivery; all use the approved mutation path in MVP |

Proposal state, approval status, execution state, and remote campaign status must not share an ambiguous single `status` field in public contracts. Use the separate lifecycles in [overview](overview.md). “Automatic read” still requires authorization; “recommend pause” never means “pause without approval,” despite the legacy constant name `STOCK_FLOOR_TO_AUTO_PAUSE`.
