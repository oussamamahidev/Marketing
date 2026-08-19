<!--
PURPOSE: Define the authoritative business basis for Maroc Affiliate advertising profitability analysis.
RESPONSIBILITY: Freezes delivered-order economics and data authority; it does not implement analytics queries or set product-owner constants.
DEPENDENCIES: BUSINESS_CONSTANTS.md, authorized Maroc Affiliate commerce data, and Meta performance data.
USED BY: P16 profitability analytics, P17 recommendations, product review, and seller-facing analysis.
TESTED BY: P00 documentation contract tests and P00 validation.
-->

# Delivered-order profitability

## Authority and scope

Maroc Affiliate profitability is based on delivered-order economics, not Meta's
attribution alone. Meta-reported conversions and Meta ROAS are informational signals:
they may support operational analysis, but they are never authoritative business
profitability measures.

Authoritative business analysis uses seller-authorized Maroc Affiliate commerce data
and, where available, combines:

- delivered revenue;
- cancellations;
- returns;
- COGS;
- delivery cost; and
- ad spend.

The analysis must retain source, seller scope, attribution-window, and freshness
metadata so a recommendation cannot present an incomplete or stale measure as fact.
Cancellation and return outcomes are commerce facts, not Meta conversion substitutes.

## Binding delivered-order economics

The binding profitability definition in `BUSINESS_CONSTANTS.md` is:

~~~text
net_revenue      = sum(delivered_order_value) - sum(returned_order_value)
true_cost        = ad_spend + (delivered_orders * DELIVERY_COST_PER_ORDER_MAD) + cogs
delivered_roas   = net_revenue / ad_spend
contribution     = net_revenue - true_cost
~~~

`BREAKEVEN_DELIVERED_ROAS` is computed per product from margin and delivery cost; it
is never hard-coded. P16 must use the binding attribution window and must label any
data limitations rather than silently substituting Meta-reported conversion or ROAS
figures.

## Product-owner decisions required before profitability implementation

The following binding constants remain product-owner decisions. P00 records them but
does not supply values or implement policies with them:

- `DELIVERY_COST_PER_ORDER_MAD`
- `PROFITABILITY_ATTRIBUTION_WINDOW_DAYS`
- `MIN_DAYS_BEFORE_PERFORMANCE_JUDGEMENT`

Until the relevant values are set, later work must fail clearly when it needs them.
P05 must not implement a deterministic policy that requires an unresolved constant;
the unresolved profitability decisions do not block P00-P04.
