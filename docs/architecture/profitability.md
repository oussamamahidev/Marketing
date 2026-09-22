# Commerce-aware profitability

## Document responsibility

This document owns the interpretation, provenance, and edge cases of the profitability model. It does not redefine the binding formula or configure amounts. It depends on [BUSINESS_CONSTANTS.md](../../BUSINESS_CONSTANTS.md), the [glossary](domain-glossary.md), and authoritative Catalog/Orders facts. P06 contracts, P16 analytics, P17 diagnosis, and all API/UI representations use it. P00 checks formula consistency; P16 tests verify cohort accounting, costs, missing-data behavior, deduplication and boundaries, and P17 evaluations verify faithful explanations.

## Authoritative formula and labels

The formula is owned by BUSINESS_CONSTANTS. Expressed with monetary inputs already converted to integer centimes:

```text
net_revenue    = sum(delivered_order_value) - sum(returned_order_value)
delivery_cost  = delivered_orders * configured_delivery_cost_centimes
true_cost      = ad_spend + delivery_cost + cogs
delivered_roas = net_revenue / ad_spend
contribution   = net_revenue - true_cost
```

`configured_delivery_cost_centimes` is the exact configuration-boundary conversion of `DELIVERY_COST_PER_ORDER_MAD`. It is not an independently configurable constant. Monetary facts and totals are stored as integer minor units under `PLATFORM_CURRENCY`; ratios use exact intermediate arithmetic and explicit display rounding, never floating-point money or Decimal database money columns.

Delivered-order ROAS is the authoritative advertising-return metric. Contribution is the monetary profitability result after advertising spend, COGS and delivery cost. The P00 request's phrase “ROAS net of ... COGS and delivery cost” is interpreted through this pair of binding metrics: subtracting those costs from ROAS's numerator would change the supplied formula and is not done here. Cancellations/returns affect recognized revenue and cost facts as described below.

Every product surface displaying provider conversion data—API field descriptions, dashboards, assistant replies, streams, recommendations and exports—must label it **“Meta-reported — informational only.”** It must not call Meta conversions delivered orders, substitute them for Orders data, or use provider ROAS as the authority for delivered profitability.

## Source facts and attribution

Each calculation carries `seller_id`, campaign/product identifiers, reporting period, attribution basis/window, currency, source IDs/versions, source timestamps, an as-of time, configuration/formula version, and completeness. Apply `PROFITABILITY_ATTRIBUTION_WINDOW_DAYS` to a reproducible commerce-to-campaign association, not to a model's guessed attribution. Use half-open UTC reporting intervals to avoid counting boundary events in adjacent windows twice.

P06/P16 must establish an explicit integration contract for which tracked campaign interaction anchors the attribution window and how competing campaign references are resolved. This information is not supplied by the project context. Until the contract is agreed and supported by commerce data, return `ATTRIBUTION_UNAVAILABLE` for campaign-level profitability; unambiguously sourced raw totals may still be shown with their scope. Do not silently adopt a new multi-touch model or match customer PII in the LLM. Preserve the agreed attribution rule/version on snapshots.

Use the same attributed order cohort for revenue and COGS/delivery costs, and the explicitly associated campaign reporting interval for ad spend. State the reporting basis and pending-delivery count; costs and future delivery outcomes can arrive at different times. Orders without reliable attribution remain unattributed and never get assigned merely to make totals reconcile. Late events revise the original cohort observation with provenance rather than crediting the same order again to a new period. Retention/backfill use `PERFORMANCE_SNAPSHOT_RETENTION_DAYS` and `SYNC_BACKFILL_MAX_DAYS`; corrections outside automatic backfill remain visible as an explicit data-quality issue requiring controlled repair.

## Order lifecycle and costs

| Fact | Accounting interpretation |
|---|---|
| Delivered order value | Revenue recognized on an actual delivery event, using the authoritative transaction amount rather than the current catalog price |
| Cancelled order | No delivered revenue. Cancellation metrics retain the source cohort and outcome; recognized delivery later reversed must be represented as a reversal, not silently dropped |
| Returned order value | Reversal/refund of previously recognized delivered revenue. Deduplicate by source event and handle partial reversals without subtracting the same amount twice |
| Refused-on-delivery | Counts as a return for risk analysis. If delivery revenue was never recognized, no revenue subtraction is booked; prevents negative revenue from subtracting a nonexistent sale |
| Delivered orders | Count of unique orders with recognized delivery events in the cohort, including those subsequently returned; later return does not erase the original delivery cost |
| COGS | Authoritative cost recognized for the cohort, net of explicit supported inventory/cost reversals. Recoverable restocked inventory and nonrecoverable goods require commerce cost facts; no blanket assumption that every return restores cost |
| Delivery cost | Delivered-order count multiplied by the configured per-order assumption. Snapshot records the policy version; updating configuration does not silently rewrite past results |
| Ad spend | Provider spend observed for the campaign/period in the required currency; recorded independently of provider conversion counts |

Catalog/Orders owners must settle discount/tax treatment and cost/reversal semantics in their P06 contract. Missing COGS or ambiguous net/gross source values produce an incomplete profitability result, not an invented value.

The binding MVP delivery model charges delivery cost only for delivered orders. It does not separately model unsuccessful delivery attempts, return shipping, COD collection fees or other operating costs unless already represented by the supplied recognized cost facts. Consequently, contribution is profitability under the stated MVP model, not a claim of complete accounting net profit. Adding such costs requires an explicit product decision and central formula/configuration update before implementation.

## Breakeven delivered ROAS

Let `R` be net delivered revenue for a product/cohort and `C` its non-advertising costs (`cogs + delivery_cost`). The amount available to cover ads is `R - C`.

```text
breakeven_ad_spend = R - C
breakeven_delivered_roas = R / (R - C)
```

The second expression is meaningful only for positive `R` and positive `R - C`. It derives the threshold from the same revenue and cost model as contribution; `BREAKEVEN_DELIVERED_ROAS` is never a global fixed number. For an eligible product without observed outcomes, a projected threshold may use its price, margin-derived COGS and configured delivery cost, but it must be labelled projected, with assumptions and provenance. Do not present an unobserved return rate as measured.

If non-advertising costs consume all revenue or more, there is no finite positive advertising-spend break-even point under that model. Return a structured unavailable/not-viable result and explanation, not infinity, an arbitrary cap or a hard-coded target. A campaign can have positive delivered ROAS while negative contribution; recommendations must show the cost evidence.

## Missing data and boundary behavior

| Condition | Required result |
|---|---|
| No ad spend | `delivered_roas` is null with `ZERO_AD_SPEND`; contribution can be calculated if other facts are complete |
| Positive spend and no revenue | Delivered ROAS is zero if the cohort data is complete; contribution reflects the recorded costs |
| Missing spend, COGS, delivery configuration or currency mismatch | Affected profitability metrics are null with a stable reason/completeness field; never substitute zero or Meta conversions |
| Returns exceed delivered value in the same recognized cohort | Flag inconsistent source accounting; do not silently clamp, double-subtract or provide confident profitability diagnosis |
| Partial refunds, repeated events or out-of-order return/delivery events | Deduplicate, reconcile source history and make completeness explicit before computing a final result |
| Insufficient order sample | Suppress quoted cancellation/return rates below MIN_ORDERS_FOR_RATE_CONFIDENCE; state “insufficient data” |
| Campaign younger than MIN_DAYS_BEFORE_PERFORMANCE_JUDGEMENT | Show factual measurements and freshness, but refuse performance diagnosis |
| Pending deliveries or incomplete synchronization | Label snapshot provisional; include missing facts and source time so recommendations cannot imply certainty |
| Assumption changed | Retain configuration version; explicitly recalculate/revise snapshots if requested, preserving prior evidence |

Cancellation/return-rate denominators must be explicit cohort fields agreed with Orders: confirmation-eligible orders for cancellation, and delivery-attempted orders for returns including refusals. Apply `MIN_ORDERS_FOR_RATE_CONFIDENCE` to each metric's own eligible cohort. Where those facts are unavailable, the rate is unavailable. Do not add percentages computed over incompatible denominators or treat them as direct ROAS inputs.

## Required implementation evidence

P16 must cover normal delivery, cancellation without revenue, return after delivery, refusal without recognized revenue, partial refund, corrected COGS, duplicate events, attribution gaps, zero spend, invalid currency, late fulfilment, and configuration-version changes. Compare exact monetary totals and derived ratios to the binding formula. P17 evaluates recommendations against those fixtures and rejects invented rates, unsupported causal claims and unlabelled Meta conversion metrics. These are future implementation tests; P00 does not claim they have run.
