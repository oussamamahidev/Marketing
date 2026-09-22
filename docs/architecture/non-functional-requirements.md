# Non-functional requirements

## Document responsibility

This document owns verifiable quality, security, reliability, and boundary behavior requirements. It does not implement controls or invent numeric service targets. It depends on [PROJECT_CONTEXT.md](../../PROJECT_CONTEXT.md), [BUSINESS_CONSTANTS.md](../../BUSINESS_CONSTANTS.md), [overview](overview.md), and [profitability](profitability.md). Implementation and operations phases use it as acceptance guidance. P00 checks completeness/consistency; the phase-specific checks below verify actual behavior after implementation.

## Targets and verification

All numeric targets resolve to named constants. The finalized values are initial MVP business assumptions and must be reviewed with real operational data before production. No unapproved latency percentile, uptime percentage, concurrency capacity, or additional retention period is asserted here. P21/P22 must establish a measured capacity profile and agree any additional numerical SLOs centrally before production sign-off.

| ID | Requirement / target | Evidence and delivery gate |
|---|---|---|
| NFR-01 | Framework-independent domain and explicit application ports; thin HTTP/worker handlers | P01/P05 architecture/import review; no infrastructure or web framework types in domain |
| NFR-02 | Every seller-owned lookup/write and referenced resource is scoped to verified `seller_id` | P04 and later API/repository tests attempt cross-seller access, forged task scope and unauthorized account links |
| NFR-03 | Financial mutations require current authorization, deterministic validation, exact-payload approval, idempotency, and durable audit | P11–P14 negative-path tests remove each precondition; no gateway write may occur |
| NFR-04 | Concurrent approvals/executions cannot exceed seller budget; uncertain outcomes retain reservations | P05/P12/P13 PostgreSQL integration tests use concurrent claims and crashes at send/commit boundaries |
| NFR-05 | Secrets stay inside identity/crypto/integration boundaries | P07/P10/P20 tests inspect API errors, logs, traces, LLM payloads, fixtures and streaming frames for leakage |
| NFR-06 | Monetary storage is integer centimes in PLATFORM_CURRENCY; currency mismatch blocks publication | P03/P05/P08 tests reject floats, invalid precision and mismatched Meta currencies; no implicit FX |
| NFR-07 | Current source facts are required before mutation; unavailable authoritative persistence or safety dependencies block dispatch | P12 fault injection for PostgreSQL, permissions, inventory, account state, approval/audit writes and kill-switch lookup |
| NFR-08 | External side effects remain recoverable after queue loss, duplicate delivery or process interruption | P12/P13/P15 tests replay persisted dispatch intents and reconcile unknown outcomes without duplicate writes |
| NFR-09 | AI execution is bounded and structured; context sources and evidence are inspectable | P10/P17/P18 evaluation cases verify schemas, tool allowlist, limits, injection resistance and insufficient-data responses |
| NFR-10 | Performance/commerce snapshots are sourced, deduplicated, time-bounded, and visibly incomplete when required facts are absent | P15/P16 contract tests cover repeated sync, late returns, missing intervals and revisions |
| NFR-11 | Delivered-order ROAS and contribution follow the authoritative formula; Meta conversions are visibly informational | P16 unit/API/UI-contract checks compare commerce fixtures to formula, including no-spend/no-revenue cases |
| NFR-12 | Recovery meets RTO_MINUTES and RPO_MINUTES; retention/frequency follow BACKUP_RETENTION_DAYS and RESTORE_TEST_FREQUENCY_DAYS | P23/DR01 measured isolated restore, integrity/tenant checks, worker suppression and reconciliation before mutation resume |
| NFR-13 | Structured logs and traces correlate API, graph, worker, gateway and reconciliation execution | P02/P21 checks use request_id/correlation_id and safe execution references across process boundaries |
| NFR-14 | Mutable business state is distinct from append-only audit evidence | P12/P19 persistence tests reject ordinary update/delete of audit events; privileged access is controlled and operationally monitored |
| NFR-15 | Typed configuration fails startup on missing/invalid required settings | P02 config tests cover missing values, wrong types and invalid relationships; no silent financial-policy fallback |
| NFR-16 | Restore/redeploy must not turn old approvals or lost local history into duplicate spending | P13/P22/P23 test expiry, durable operation identity and reconcile remote activity after the restore point |

## Configuration boundaries

Tests at the implementing phase cover below, at, and above each named numeric boundary using configuration, not copied literals. Exact-boundary acceptance must match the rule below.

| Area | Named configuration and semantics |
|---|---|
| Budget | Daily budget is at least MIN_DAILY_BUDGET_MAD and at most MAX_DAILY_BUDGET_MAD; active plus in-flight reserved seller budget is at most MAX_DAILY_BUDGET_PER_SELLER_MAD. Increases are at most MAX_BUDGET_INCREASE_PCT_PER_ACTION and changes occur no earlier than MIN_HOURS_BETWEEN_BUDGET_CHANGES. BUDGET_CHANGE_REQUIRES_APPROVAL is always true |
| Product eligibility | Creation/resume requires stock at least MIN_STOCK_UNITS_TO_ADVERTISE and gross margin at least MIN_GROSS_MARGIN_PCT. Stock strictly below STOCK_FLOOR_TO_AUTO_PAUSE produces a pause recommendation requiring approval. Rates strictly above MAX_ACCEPTABLE_CANCELLATION_RATE_PCT / MAX_ACCEPTABLE_RETURN_RATE_PCT are high-risk flags; these flags alone do not invent an additional publication ban |
| Evidence | Below MIN_ORDERS_FOR_RATE_CONFIDENCE, numerical cancellation/return-rate claims are withheld as insufficient data. Before MIN_DAYS_BEFORE_PERFORMANCE_JUDGEMENT, the AI refuses performance diagnosis; raw factual status remains viewable |
| Profitability | Use PROFITABILITY_ATTRIBUTION_WINDOW_DAYS, DELIVERY_COST_PER_ORDER_MAD, and computed BREAKEVEN_DELIVERED_ROAS under the documented model |
| AI bounds | Enforce MAX_GRAPH_STEPS, MAX_STRUCTURED_OUTPUT_RETRIES, LLM_REQUEST_TIMEOUT_SECONDS, MAX_INPUT_TOKENS_PER_RUN, MAX_OUTPUT_TOKENS_PER_RUN, MAX_SELLER_INSTRUCTION_CHARS; exceeding a hard bound stops the operation. Token/run budgets count cumulatively across nodes and retries. Output retries are bounded additional attempts, not a way to reset run budgets |
| Seller AI quotas | Enforce MAX_AI_PROPOSALS_PER_SELLER_PER_DAY and MAX_LLM_COST_PER_SELLER_PER_DAY_MAD atomically before dispatch, reserving bounded usage for concurrent runs and reconciling actual usage. Use UTC calendar-day buckets. Missing provider-cost conversion/usage evidence blocks cost-controlled generation; no invented exchange rate or currency conversion is allowed |
| Execution | Use IDEMPOTENCY_KEY_TTL_HOURS, META_WRITE_TIMEOUT_SECONDS, MAX_RETRIES_META_WRITE, EXECUTING_STATE_STALE_AFTER_MINUTES, RECONCILIATION_SCAN_INTERVAL_MINUTES, and APPROVAL_PAYLOAD_TTL_MINUTES. Approval is invalid at or after expiry; stale execution at or beyond its cutoff requires reconciliation. Retry limits apply only to known-safe writes |
| Synchronization | Follow PERFORMANCE_SYNC_INTERVAL_MINUTES, PERFORMANCE_SNAPSHOT_RETENTION_DAYS, META_API_RATE_LIMIT_BUFFER_PCT and SYNC_BACKFILL_MAX_DAYS. Preserve provenance and explicit gaps; the configured cadence is a scheduling objective, not permission to use old safety facts at dispatch |
| API | DEFAULT_PAGE_SIZE must not exceed MAX_PAGE_SIZE; enforce RATE_LIMIT_AUTHENTICATED_PER_MINUTE, RATE_LIMIT_AI_ENDPOINTS_PER_MINUTE and SSE_MAX_STREAM_DURATION_SECONDS. Quota/circuit denials use stable errors and bounded retry advice |

Typed config validates positive durations/capacities, nonnegative retries/costs, valid percentage ranges, minimum budget no greater than maximum, campaign maximum no greater than seller maximum, stock pause floor below creation stock threshold, and recovery/retention consistency. Monetary MAD configuration is parsed exactly and converted to integer centimes at the config boundary. Domain policies consume a typed policy object; they do not import environment variables or a framework settings object.

Provider pricing needed to meter LLM usage in MAD is an unresolved integration contract for P10. The ad-account FX policy remains unchanged; an unavailable auditable MAD cost basis must not silently bypass the LLM cost cap. Add any necessary pricing configuration centrally after the provider contract is known.

## Authorization, secrets, and untrusted content

Validate trusted issuer/audience/session and seller membership through the platform identity contract. Apply deny-by-default action permissions, ownership checks and ABAC constraints such as current account access and mutation kill-switch state. A missing role or unverifiable identity never defaults to a service/admin principal. Administrative cross-tenant views need explicit permissions, narrow projections and audit.

Resolve OAuth credentials through tenant-bound encrypted references inside Infrastructure. Keep encryption keys separate from encrypted tokens, support revocation/reconnection and controlled key rotation, and avoid presenting secrets through frontend, LLM, logs, traces, error reports or audit payloads. OAuth callbacks must bind state to the initiating authorized seller session and reject replay/mismatched state. Concrete protocol hardening is verified against the provider contract in P07.

Seller instructions, product descriptions, creative metadata, commerce text, API responses and tool output are untrusted data. Delimit them from system instructions, validate schemas/lengths and allowlist tools/intents. AI tools receive only minimized authorized context and read capabilities. No model-produced seller ID, permission, approval, tool name or URL can authorize action or broaden context. Typed output and human approval supplement deterministic controls; neither substitutes for them.

Use allowlisted provider destinations and validate externally supplied asset URLs before fetching. P20 implements SSRF, CORS, CSRF and header policies appropriate to the chosen trusted identity transport; cookie-based state changes require CSRF protection. Rate limits and dependency checks cannot be bypassed merely to make tests pass.

## Errors and integration behavior

Use an application error envelope with `code`, safe `message`, `request_id`, and optional sanitized field details. Each provider adapter translates its exceptions into canonical errors; HTTP mappings occur in Presentation, not Domain. Async execution failures expose operation status in addition to request correlation. An unknown external outcome returns an accepted operation with explicit reconciliation status, not a misleading completed-success payload.

| HTTP/status | Stable application code examples | Semantics |
|---|---|---|
| 400 | `INVALID_REQUEST` | Malformed request syntax/protocol |
| 422 | `VALIDATION_FAILED`, `POLICY_VIOLATION`, `CURRENCY_MISMATCH` | Schema/field errors or deterministic eligibility rejection |
| 401 | `UNAUTHENTICATED` | Missing/invalid platform authentication |
| 403 | `FORBIDDEN` | Known scoped action without required permission |
| 404 | `RESOURCE_NOT_FOUND` | Missing resource within caller's tenant; cross-tenant references return the same result |
| 409 | `STATE_CONFLICT`, `VERSION_CONFLICT`, `IDEMPOTENCY_CONFLICT`, `APPROVAL_EXPIRED`, `CONNECTION_REAUTH_REQUIRED` | State mismatch or action requiring a new approved state/connection |
| 429 | `RATE_LIMITED`, `AI_QUOTA_EXCEEDED`, `AI_COST_LIMIT_EXCEEDED` | Authenticated throttling or seller generation limits |
| 502 | `UPSTREAM_INVALID_RESPONSE`, `INVALID_AI_OUTPUT` | Invalid provider contract/structured output after bounded retries |
| 503 | `DEPENDENCY_UNAVAILABLE`, `MUTATION_DISABLED` | Required dependency or dispatch gate unavailable |
| 504 | `UPSTREAM_TIMEOUT` | Known read/pre-dispatch timeout; must not imply a sent write failed |
| 202 + operation status | `RECONCILIATION_REQUIRED` | Mutation outcome uncertain; poll/read persisted operation until resolved |

Never expose stack traces, authorization headers, raw provider bodies, token-bearing URLs or unsafe external payloads. A platform authentication failure is different from an expired Meta grant; the latter requires reconnecting Meta, not misreporting the seller's platform login.

## Failure and concurrency scenarios

| Scenario | Required behavior | Verification phase |
|---|---|---|
| Missing resource | Scoped not-found; no write, no existence leak across tenants | P04/P09/P14 |
| Stale state or stale source facts | Version conflict or refresh/revalidation; invalidate approval when effective payload changes | P05/P11/P12 |
| Duplicate request/task | Same scoped payload/key returns existing operation; changed payload conflicts; redelivery never blindly repeats Meta mutation | P12/P15 |
| Timeout before confirmed dispatch | Retry only if non-application is established and original approval remains valid | P08/P12/P13 |
| Timeout after possible dispatch | Preserve IDs/reservations, set reconciliation required, perform read-based recovery | P12/P13 |
| PostgreSQL/audit unavailable | No new financial dispatch; after-send commit failure leaves recovery to durable prior execution intent | P12/P13 |
| Redis unavailable or task lost | Reads may continue where safe; generation fails closed if quotas cannot be enforced; recover work from durable intents when queue returns | P10/P15 |
| Malformed dependency response | Validate/reject typed response; do not coerce missing budget/stock into safe-looking values | P06/P08/P10 |
| Cross-seller product, creative, approval, token, account or execution reference | Deny within tenant boundary; do not fetch secret-bearing remote data for another seller | P04/P07/P11/P14 |
| Expired/revoked credentials | Block dispatch, mark reconnect required, invalidate readiness; reconcile earlier uncertain writes when authorized access returns | P07/P13 |
| Concurrent budget changes/publications | Serialize PostgreSQL reservations and version checks; exactly one claim per approval; account for unresolved spend | P05/P12 |
| Partial provider publication | Persist completed steps, do not activate unapproved content, reconcile incomplete effects; compensation is separately approved | P12/P13 |
| Cancellation during execution | Before send, cancel atomically; after possible send, reconcile. Closing an SSE connection cannot undo an operation | P13/P18 |
| Graph interrupted/resumed or retried | Reload seller scope and durable approval; tampered checkpoint cannot authorize mutation | P10/P11 |
| Out-of-order sync or late return | Deduplicate source facts; retain correction/provenance and recompute an explicitly revised snapshot | P15/P16 |
| Restore after remote writes | Suppress dispatch, reconcile external state since restore point, then explicitly restore mutation readiness | P23 |

## Logging, metrics, and operational boundaries

Use structured lifecycle and dependency-failure logs with `request_id`, `correlation_id`, safe operation references and classified error codes. Continue correlation through durable job metadata and propagation-safe tracing headers. Record state changes at appropriate severity without duplicating every poll as an error.

Never log authorization headers, OAuth tokens, encryption keys, unnecessary customer PII, or entire LLM prompts containing sensitive context. Seller/campaign identifiers are allowed in controlled logs only under the project's privacy policy; until established, minimize or pseudonymize these identifiers. No seller, campaign, request, execution, prompt or token values may become metric labels.

P00 introduces no runtime behavior and therefore adds no instrumentation or metrics code. When each operational behavior is introduced, record counters for success/failure, latency histograms for external calls and sensitive steps, and gauges for outstanding reconciliation/backlog. Use bounded labels such as operation, provider, outcome and error class. P21 integrates OpenTelemetry, Prometheus/Grafana-compatible metrics, Sentry and alert definitions; it does not postpone basic mutation logging until then.

Readiness reflects required dependency availability without disclosing secrets. Liveness must distinguish a responsive process from a ready-to-mutate service. PostgreSQL migrations and deploy/rollback procedures must preserve approval/execution semantics; rollback cannot erase remote effects. Backups require controlled access, tested restore, retained key access, and recovery evidence against the configured objectives.
