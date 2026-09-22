"""Bounded-label DB operation metrics; no URL, SQL, tenant or request labels.

Database lifecycle helpers record these; a later telemetry endpoint can expose
the standard registry. No new public metrics route is introduced in P03.
"""

from prometheus_client import Counter, Histogram

CHECKS = Counter("marketing_ai_database_checks_total", "Database readiness outcomes", ["outcome"])
CHECK_DURATION = Histogram(
    "marketing_ai_database_check_duration_seconds", "Database readiness latency", ["outcome"]
)
TRANSACTIONS = Counter(
    "marketing_ai_database_transactions_total", "Transaction context outcomes", ["outcome"]
)
TRANSACTION_DURATION = Histogram(
    "marketing_ai_database_transaction_duration_seconds", "Transaction context latency", ["outcome"]
)
