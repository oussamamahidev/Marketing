# BUSINESS_CONSTANTS.md — Binding Numeric Limits (single source of truth)

Every prompt phrase such as "configured maximum", "threshold", "limit", "cadence", or "boundary" resolves against this file.

**Rules for the coding agent:**
1. Never invent a value that belongs here. If a constant is unset, fail startup with a clear configuration error.
2. Load these through `core/config.py` with typed validation. No literals scattered in domain or infrastructure code.
3. Any policy in `domain/advertising/policies.py` must reference a named constant, never a magic number.
4. Tests must assert behaviour **at** the boundary, **below** it, and **above** it, using the named constant — not a hard-coded copy.

## Configuration status and ownership

The product owner approved all values below as the finalized initial MVP configuration on 2026-09-20. These are MVP defaults/business assumptions, not measured operating guarantees. Revisit them against actual Maroc Affiliate operational data before production launch. Changes belong in this centralized specification and the typed `core/config.py` configuration mechanism; domain logic and tests reference named constants rather than copied numeric values.

`DELIVERY_COST_PER_ORDER_MAD` is an initial business assumption. Replace it with the actual Maroc Affiliate average delivery cost when available through configuration, without changing domain logic. Record the applicable configuration version in profitability snapshots so later changes do not silently rewrite historical results.

Every P00 numeric business limit below is resolved. P03 additionally requires the operational database settings in section 11, whose deployment values are pending an owner decision. `BREAKEVEN_DELIVERED_ROAS` remains intentionally computed per product, not an unset configuration value. Missing or invalid required settings must fail startup; approval requirements cannot be disabled.

---

## 1. Currency and money

| Constant | Value | Notes |
|---|---|---|
| `PLATFORM_CURRENCY` | `MAD` | Moroccan dirham. All internal amounts stored as integer minor units (centimes). |
| `MONEY_STORAGE` | integer centimes | Never float. Never `Decimal` at the DB boundary. |
| `META_ACCOUNT_CURRENCY_POLICY` | reject mismatch | If the seller's Meta ad account currency is not `MAD`, block publication and surface a clear error. Do not silently convert. |
| `FX_CONVERSION` | not supported in MVP | Explicitly out of scope. |

## 2. Budget policy (enforced deterministically in P05, revalidated in P12)

| Constant | Value | Notes |
|---|---|---|
| `MIN_DAILY_BUDGET_MAD` | `50` | Below Meta's practical delivery floor, campaigns underdeliver. |
| `MAX_DAILY_BUDGET_MAD` | `500` | Hard ceiling for AI-proposed budgets in MVP. |
| `MAX_DAILY_BUDGET_PER_SELLER_MAD` | `2000` | Sum across all that seller's active campaigns. |
| `MAX_BUDGET_INCREASE_PCT_PER_ACTION` | `25` | Caps any single approved increase. |
| `MIN_HOURS_BETWEEN_BUDGET_CHANGES` | `24` | Prevents thrash and Meta learning-phase reset. |
| `BUDGET_CHANGE_REQUIRES_APPROVAL` | `true` | Non-negotiable. No configuration may disable this. |

## 3. Product eligibility (COD-specific — this is the differentiator)

| Constant | Value | Notes |
|---|---|---|
| `MIN_STOCK_UNITS_TO_ADVERTISE` | `20` | Below this, refuse to create or resume a campaign. |
| `STOCK_FLOOR_TO_AUTO_PAUSE` | `5` | Recommend pause; never auto-pause without approval in MVP. |
| `MIN_GROSS_MARGIN_PCT` | `30` | Margin after COGS, before ad spend and delivery cost. |
| `MAX_ACCEPTABLE_CANCELLATION_RATE_PCT` | `35` | COD confirmation failure. Flag the product as high-risk above this. |
| `MAX_ACCEPTABLE_RETURN_RATE_PCT` | `15` | Refused-on-delivery counts as a return. |
| `MIN_ORDERS_FOR_RATE_CONFIDENCE` | `30` | Below this sample size, the AI must state "insufficient data" instead of quoting a rate. |
| `DELIVERY_COST_PER_ORDER_MAD` | `35` | Owner-approved initial MVP assumption; replace with the actual average through centralized configuration. |

## 4. Profitability definition (P16)

Delivered-order ROAS is the authoritative metric. Meta's reported conversions are informational only.

```
net_revenue      = sum(delivered_order_value) - sum(returned_order_value)
true_cost        = ad_spend + (delivered_orders * DELIVERY_COST_PER_ORDER_MAD) + cogs
delivered_roas   = net_revenue / ad_spend
contribution     = net_revenue - true_cost
```

| Constant | Value | Notes |
|---|---|---|
| `PROFITABILITY_ATTRIBUTION_WINDOW_DAYS` | `14` | COD delivery lag means Meta's 7-day window understates truth. |
| `BREAKEVEN_DELIVERED_ROAS` | computed | Derived per product from margin and delivery cost. Never hard-coded. |
| `MIN_DAYS_BEFORE_PERFORMANCE_JUDGEMENT` | `3` | The AI must refuse to diagnose a campaign younger than this. |

## 5. AI limits (P10, P17, P18)

| Constant | Value | Notes |
|---|---|---|
| `MAX_GRAPH_STEPS` | `12` | Hard termination. Exceeding it is a failure, not a retry. |
| `MAX_STRUCTURED_OUTPUT_RETRIES` | `2` | Then `INVALID_AI_OUTPUT`. |
| `LLM_REQUEST_TIMEOUT_SECONDS` | `60` | |
| `MAX_INPUT_TOKENS_PER_RUN` | `20000` | Truncate authoritative context deterministically, never randomly. |
| `MAX_OUTPUT_TOKENS_PER_RUN` | `2000` | |
| `MAX_AI_PROPOSALS_PER_SELLER_PER_DAY` | `20` | Abuse and cost control. Returns 429. |
| `MAX_LLM_COST_PER_SELLER_PER_DAY_MAD` | `10` | Circuit-breaks AI generation for that seller when exceeded; the rest of the product stays functional. |
| `MAX_SELLER_INSTRUCTION_CHARS` | `1000` | Rejected above this, not silently truncated. |

## 6. Reliability and reconciliation (P12, P13)

| Constant | Value | Notes |
|---|---|---|
| `IDEMPOTENCY_KEY_TTL_HOURS` | `72` | |
| `META_WRITE_TIMEOUT_SECONDS` | `30` | |
| `MAX_RETRIES_META_WRITE` | `3` | Exponential backoff with jitter. Never retry a write of unknown outcome — reconcile first. |
| `EXECUTING_STATE_STALE_AFTER_MINUTES` | `10` | Scanner moves it to `RECONCILIATION_REQUIRED`. |
| `RECONCILIATION_SCAN_INTERVAL_MINUTES` | `5` | |
| `APPROVAL_PAYLOAD_TTL_MINUTES` | `30` | Approval expires; stock and budget are revalidated at publish regardless. |

## 7. Synchronisation cadence (P15, P16)

| Constant | Value | Notes |
|---|---|---|
| `PERFORMANCE_SYNC_INTERVAL_MINUTES` | `60` | |
| `PERFORMANCE_SNAPSHOT_RETENTION_DAYS` | `400` | |
| `META_API_RATE_LIMIT_BUFFER_PCT` | `20` | Stay this far below Meta's published limit. |
| `SYNC_BACKFILL_MAX_DAYS` | `30` | |

## 8. API limits (P14, P20)

| Constant | Value | Notes |
|---|---|---|
| `DEFAULT_PAGE_SIZE` | `20` | Must not exceed `MAX_PAGE_SIZE`. |
| `MAX_PAGE_SIZE` | `100` | Hard maximum for paginated requests. |
| `RATE_LIMIT_AUTHENTICATED_PER_MINUTE` | `120` | |
| `RATE_LIMIT_AI_ENDPOINTS_PER_MINUTE` | `5` | |
| `SSE_MAX_STREAM_DURATION_SECONDS` | `300` | |

## 9. Recovery objectives (P23, DR01)

| Constant | Value | Notes |
|---|---|---|
| `RTO_MINUTES` | `60` | DR01 fails if the measured restore exceeds this. |
| `RPO_MINUTES` | `15` | Drives PITR/WAL retention configuration. |
| `BACKUP_RETENTION_DAYS` | `30` | |
| `RESTORE_TEST_FREQUENCY_DAYS` | `90` | An untested backup is not a backup. |

## 10. External dependency lead times (schedule risk — not code)

These are not configuration. They are calendar risks that block launch regardless of code readiness.

| Item | Owner | Lead time | Blocks |
|---|---|---|---|
| Meta Business verification | Product owner | 1-3 weeks | P07 |
| Meta App Review for `ads_management` + `ads_read` scopes | Product owner | 2-6 weeks, may require re-submission | P08 real accounts, P12 |
| Meta advertising policy review of generated ad copy categories | Product owner | Ongoing | P10 acceptance |
| Managed PostgreSQL + Redis provisioning | Engineering | Days | P03, P15 |

**Start Meta verification and app review at P00, in parallel with P01.** It is the single most likely cause of a finished system that cannot launch.

## 11. Database operational configuration (P03)

The following required settings are owned by the centralized configuration mechanism. Their initial deployment values have not been approved. They intentionally have no runtime defaults; `.env.example` leaves them empty and application startup rejects missing/empty values.

- `DATABASE_POOL_SIZE`: positive retained connection count per engine/process.
- `DATABASE_MAX_OVERFLOW`: non-negative additional connection count; unlimited overflow is forbidden.
- `DATABASE_POOL_TIMEOUT_SECONDS`: positive wait limit when the pool is exhausted.
- `DATABASE_CONNECT_TIMEOUT_SECONDS`: positive driver connection timeout.
- `DATABASE_READINESS_TIMEOUT_SECONDS`: positive deadline for the entire database readiness check.

Maximum concurrent pooled connections per process equal pool size plus maximum overflow; multiple app/worker processes multiply that total. Size against PostgreSQL capacity, migration/admin headroom and measured workloads before production. The proposed initial values remain a pending conversation decision, not active configuration. Synthetic values in test fixtures are isolated harness inputs and are not deployment defaults.
