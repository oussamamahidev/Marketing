"""Documentation contract tests for P00.

PURPOSE: Detect regressions in the frozen architecture, safety requirements, glossary,
and ADR records without introducing product behavior.
RESPONSIBILITY: Verifies documentation structure and required commitments; it does not
test unimplemented application, database, worker, or external-integration behavior.
DEPENDENCIES: Python standard library and the P00 documentation files.
USED BY: P00-T and later regression test runs.
TESTED BY: pytest/unittest discovery.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
ARCHITECTURE_DIRECTORY = REPOSITORY_ROOT / "docs" / "architecture"
ADR_DIRECTORY = REPOSITORY_ROOT / "docs" / "adr"

REQUIRED_DOCUMENTS = (
    ARCHITECTURE_DIRECTORY / "overview.md",
    ARCHITECTURE_DIRECTORY / "domain-glossary.md",
    ARCHITECTURE_DIRECTORY / "non-functional-requirements.md",
    ARCHITECTURE_DIRECTORY / "profitability.md",
    ADR_DIRECTORY / "ADR-001-modular-monolith.md",
    ADR_DIRECTORY / "ADR-002-postgresql.md",
    ADR_DIRECTORY / "ADR-003-langgraph-state-machine.md",
    ADR_DIRECTORY / "ADR-004-celery-before-temporal.md",
    ADR_DIRECTORY / "ADR-005-meta-gateway-abstraction.md",
    ADR_DIRECTORY / "ADR-006-human-approval.md",
    ADR_DIRECTORY / "ADR-007-no-vector-db-mvp.md",
)

REQUIRED_ADRS = (
    "ADR-001-modular-monolith.md",
    "ADR-002-postgresql.md",
    "ADR-003-langgraph-state-machine.md",
    "ADR-004-celery-before-temporal.md",
    "ADR-005-meta-gateway-abstraction.md",
    "ADR-006-human-approval.md",
    "ADR-007-no-vector-db-mvp.md",
)


class P00ArchitectureDocumentationTests(unittest.TestCase):
    """Regression tests for the P00 architecture freeze."""

    def read_document(self, document_path: Path) -> str:
        return document_path.read_text(encoding="utf-8")

    def assert_contains_all(
        self, text: str, required_fragments: tuple[str, ...]
    ) -> None:
        normalized_text = text.casefold()
        for fragment in required_fragments:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment.casefold(), normalized_text)

    def test_required_documents_exist_and_declare_responsibility(self) -> None:
        for document_path in REQUIRED_DOCUMENTS:
            with self.subTest(document=document_path.name):
                self.assertTrue(document_path.is_file())
                document = self.read_document(document_path)
                for responsibility_marker in (
                    "PURPOSE:",
                    "RESPONSIBILITY:",
                    "DEPENDENCIES:",
                    "USED BY:",
                    "TESTED BY:",
                ):
                    self.assertIn(responsibility_marker, document)

    def test_readme_architecture_links_are_local_and_resolve(self) -> None:
        readme_path = REPOSITORY_ROOT / "README.md"
        readme = self.read_document(readme_path)
        targets = re.findall(r"\[[^]]+\]\(([^)]+)\)", readme)
        required_p00_targets = (
            "docs/architecture/overview.md",
            "docs/architecture/domain-glossary.md",
            "docs/architecture/non-functional-requirements.md",
            "docs/architecture/profitability.md",
            "docs/adr/",
        )

        for target in targets:
            with self.subTest(target=target):
                local_target = target.split("#", maxsplit=1)[0].strip("<>")
                if local_target.startswith(("http://", "https://", "mailto:")):
                    continue
                target_path = (readme_path.parent / local_target).resolve()
                self.assertTrue(target_path.is_relative_to(REPOSITORY_ROOT))
                self.assertTrue(target_path.exists())

        for required_target in required_p00_targets:
            with self.subTest(required_target=required_target):
                self.assertIn(required_target, targets)
                self.assertTrue((readme_path.parent / required_target).exists())

    def test_each_adr_has_the_required_decision_record_sections(self) -> None:
        required_sections = (
            "## Context",
            "## Decision",
            "## Alternatives considered",
            "## Consequences",
            "## Replacement trigger",
        )

        for adr_name in REQUIRED_ADRS:
            with self.subTest(adr=adr_name):
                document = self.read_document(ADR_DIRECTORY / adr_name)
                self.assertIn("**Status:** Accepted", document)
                for section in required_sections:
                    self.assertIn(section, document)

    def test_overview_freezes_the_required_architecture_and_data_flows(self) -> None:
        overview = self.read_document(ARCHITECTURE_DIRECTORY / "overview.md")

        self.assert_contains_all(
            overview,
            (
                "Presentation -> Application -> Domain <- Infrastructure",
                "HTTP/Worker -> Application Use Case -> Domain Policies -> Repository/Gateway -> External/DB",
                "Authorized Context",
                "LangGraph state machine",
                "LLM structured output",
                "deterministic validation",
                "human approval",
                "application mutation",
                "PostgreSQL",
                "Redis",
                "MetaAdsGateway",
            ),
        )

    def test_architecture_baseline_and_typed_integration_ports_are_explicit(
        self,
    ) -> None:
        overview = self.read_document(ARCHITECTURE_DIRECTORY / "overview.md")
        postgresql_adr = self.read_document(ADR_DIRECTORY / "ADR-002-postgresql.md")

        self.assert_contains_all(
            overview,
            (
                "Python/FastAPI modular monolith",
                "Dockerized application and worker processes",
                "Identity",
                "Catalog",
                "Inventory and warehouse",
                "Orders",
                "Content Hub",
                "CatalogReader",
                "InventoryReader",
                "OrdersReader",
                "ContentHubReader",
                "StructuredLlmProvider",
                "Proposal, Approval, Execution, Snapshot, and Audit repositories",
                "raw OAuth tokens",
                "raw external payloads",
            ),
        )
        self.assert_contains_all(postgresql_adr, ("SQLAlchemy 2.x", "Alembic"))

    def test_overview_defines_separate_proposal_and_execution_safety_states(
        self,
    ) -> None:
        overview = self.read_document(ARCHITECTURE_DIRECTORY / "overview.md")

        self.assert_contains_all(
            overview,
            (
                "Proposal and execution are separate state machines",
                "PendingApproval",
                "Approved",
                "Superseded",
                "ExecutionRequested",
                "PendingConfirmation",
                "Reconciliation",
                "Any payload, creative, product, budget, targeting, permissions, stock",
            ),
        )

    def test_execution_transition_contract_rejects_unsafe_implicit_paths(self) -> None:
        overview = self.read_document(ARCHITECTURE_DIRECTORY / "overview.md")
        execution_section = overview.split("### Execution state", maxsplit=1)[1].split(
            "## Safety invariants", maxsplit=1
        )[0]

        required_transition_rows = (
            "| NotRequested | No publish action exists. | ExecutionRequested, Cancelled |",
            "| ExecutionRequested | An approved payload and idempotency key were recorded. | Dispatching, Cancelled, FinalFailure |",
            "| Dispatching | The Meta gateway call is in progress. | Succeeded, PendingConfirmation, RetryableFailure, FinalFailure |",
            "| PendingConfirmation | A timeout or ambiguous external outcome prevents a reliable result. | Reconciliation |",
            "| Reconciliation | A worker is resolving an ambiguous or stuck execution. | Succeeded, RetryableFailure, FinalFailure, PendingConfirmation |",
        )
        for transition_row in required_transition_rows:
            with self.subTest(transition_row=transition_row):
                self.assertIn(transition_row, execution_section)

        self.assert_contains_all(
            execution_section,
            (
                "No execution transition outside this table is valid",
                "same logical idempotency key",
                "already dispatched or ambiguous external mutation was cancelled",
                "still-valid Approved proposal",
            ),
        )

    def test_sensitive_mutation_gate_is_explicit_and_non_authoritative_ai_is_preserved(
        self,
    ) -> None:
        overview = self.read_document(ARCHITECTURE_DIRECTORY / "overview.md")
        human_approval_adr = self.read_document(
            ADR_DIRECTORY / "ADR-006-human-approval.md"
        )
        combined = f"{overview}\n{human_approval_adr}"

        self.assert_contains_all(
            combined,
            (
                "LLM recommendation is never",
                "deterministic policy validation",
                "exact-payload",
                "idempotency",
                "audit",
                "immediately revalidate",
                "fail closed",
                "ambiguous",
                "reconciliation",
            ),
        )

    def test_glossary_defines_the_required_shared_terms(self) -> None:
        glossary = self.read_document(ARCHITECTURE_DIRECTORY / "domain-glossary.md")

        self.assert_contains_all(
            glossary,
            (
                "Seller",
                "Principal",
                "Meta connection",
                "Ad account link",
                "Campaign proposal",
                "Approval",
                "Campaign execution",
                "Reconciliation",
                "Recommendation",
                "Performance snapshot",
                "Delivered-order ROAS",
                "Audit event",
            ),
        )

        definitions = {
            columns[0].strip(): columns[1].strip()
            for line in glossary.splitlines()
            if line.startswith("|")
            and not line.startswith("| ---")
            and len(columns := line.strip("|").split("|")) == 2
            and columns[0].strip() != "Term"
        }
        for required_term in (
            "Seller",
            "Principal",
            "Meta connection",
            "Ad account link",
            "Campaign proposal",
            "Approval",
            "Campaign execution",
            "Reconciliation",
            "Recommendation",
            "Performance snapshot",
            "Delivered-order ROAS",
            "Audit event",
        ):
            with self.subTest(term=required_term):
                self.assertIn(required_term, definitions)
                self.assertTrue(definitions[required_term])

    def test_non_functional_requirements_cover_security_errors_metrics_and_failures(
        self,
    ) -> None:
        requirements = self.read_document(
            ARCHITECTURE_DIRECTORY / "non-functional-requirements.md"
        )

        self.assert_contains_all(
            requirements,
            (
                "seller_id",
                "prompt-injection",
                "OAuth tokens",
                "request_id",
                "stable machine-readable **code** and a **request_id**",
                "401",
                "403",
                "404",
                "409",
                "429",
                "502",
                "503",
                "504",
                "validation_error",
                "external_outcome_ambiguous",
                "structured logs",
                "OpenTelemetry",
                "low-cardinality",
                "timeout",
                "malformed dependency response",
                "expired credentials",
                "concurrent update",
                "partial failure",
                "cancellation or retry",
            ),
        )

    def test_error_contract_requires_request_id_codes_and_stack_trace_redaction(
        self,
    ) -> None:
        requirements = self.read_document(
            ARCHITECTURE_DIRECTORY / "non-functional-requirements.md"
        )
        error_contract = requirements.split("## Error contract", maxsplit=1)[1].split(
            "## Logging, tracing, and metrics", maxsplit=1
        )[0]

        self.assertIn(
            "Every application error response uses a stable machine-readable **code** and a **request_id**",
            error_contract,
        )
        self.assertIn(
            "correlation_id may supplement tracing but never replaces request_id",
            error_contract,
        )
        self.assertNotIn("request_id or correlation_id", error_contract.casefold())
        self.assertIn("stack traces", error_contract)
        self.assert_contains_all(
            error_contract,
            (
                "invalid_request",
                "validation_error",
                "unauthenticated",
                "forbidden",
                "resource_not_found",
                "state_conflict",
                "external_outcome_ambiguous",
                "rate_limited",
                "upstream_bad_gateway",
                "upstream_unavailable",
                "upstream_timeout",
            ),
        )

    def test_admin_controls_require_explicit_capability_and_verified_scope(
        self,
    ) -> None:
        overview = self.read_document(ARCHITECTURE_DIRECTORY / "overview.md")
        requirements = self.read_document(
            ARCHITECTURE_DIRECTORY / "non-functional-requirements.md"
        )
        glossary = self.read_document(ARCHITECTURE_DIRECTORY / "domain-glossary.md")
        combined = f"{overview}\n{requirements}\n{glossary}"

        self.assert_contains_all(
            combined,
            (
                "explicit marketing_admin capability",
                "deny-by-default",
                "platform scope",
                "seller scope",
                "tenant-scoped kill switch",
                "does not bypass deterministic policy",
                "exact-payload seller approval",
                "immutable-audit-event",
            ),
        )

    def test_mvp_non_goals_and_all_required_replacement_triggers_remain_explicit(
        self,
    ) -> None:
        overview = self.read_document(ARCHITECTURE_DIRECTORY / "overview.md")
        postgresql_adr = self.read_document(ADR_DIRECTORY / "ADR-002-postgresql.md")
        celery_adr = self.read_document(
            ADR_DIRECTORY / "ADR-004-celery-before-temporal.md"
        )
        monolith_adr = self.read_document(ADR_DIRECTORY / "ADR-001-modular-monolith.md")
        out_of_scope = overview.split("### Out of scope for the MVP", maxsplit=1)[
            1
        ].split("## Architecture and dependencies", maxsplit=1)[0]

        self.assert_contains_all(
            out_of_scope,
            (
                "Kafka",
                "Kubernetes",
                "microservices",
                "Temporal",
                "vector database",
                "RAG",
            ),
        )
        self.assert_contains_all(
            overview,
            (
                "Celery + Redis jobs",
                "Modular monolith",
                "PostgreSQL performance analytics",
            ),
        )
        self.assert_contains_all(
            postgresql_adr,
            ("specialized analytical storage", "Replacement trigger"),
        )
        self.assert_contains_all(celery_adr, ("Temporal", "Replacement trigger"))
        self.assert_contains_all(
            monolith_adr, ("selective service", "Replacement trigger")
        )

    def test_v2_architecture_and_meta_provider_boundaries_are_explicit(self) -> None:
        overview = self.read_document(ARCHITECTURE_DIRECTORY / "overview.md")
        requirements = self.read_document(
            ARCHITECTURE_DIRECTORY / "non-functional-requirements.md"
        )
        postgresql_adr = self.read_document(ADR_DIRECTORY / "ADR-002-postgresql.md")
        celery_adr = self.read_document(
            ADR_DIRECTORY / "ADR-004-celery-before-temporal.md"
        )
        meta_gateway_adr = self.read_document(
            ADR_DIRECTORY / "ADR-005-meta-gateway-abstraction.md"
        )
        combined = (
            f"{overview}\n{requirements}\n{postgresql_adr}\n{celery_adr}\n"
            f"{meta_gateway_adr}"
        )

        self.assert_contains_all(
            combined,
            (
                "existing Maroc Affiliate identity",
                "Python/FastAPI modular monolith",
                "PostgreSQL",
                "Redis",
                "SQLAlchemy 2.x",
                "Alembic",
                "LangGraph",
                "Celery with Redis",
                "Temporal",
                "MetaAdsGateway",
                "provider-neutral port contracts",
                "MCP protocol details",
                "Meta SDK types",
                "RBAC",
                "ownership",
                "selected ABAC policies",
                "LLM recommendation is never",
                "Prometheus/Grafana",
                "error tracking",
            ),
        )

    def test_v2_seller_isolation_and_write_action_safety_gate_are_complete(
        self,
    ) -> None:
        overview = self.read_document(ARCHITECTURE_DIRECTORY / "overview.md")
        safety_gate = overview.split(
            "### Mandatory write-action safety gate", maxsplit=1
        )[1].split("### Performance and profitability flow", maxsplit=1)[0]

        self.assert_contains_all(
            overview,
            (
                "Seller A must never access Seller B campaigns, approvals, creatives, metrics, Meta connections, tokens, recommendations",
                "An authorized read tool may execute automatically",
            ),
        )

        required_steps = (
            "**Authorization**",
            "**Current authoritative data**",
            "**Deterministic business validation**",
            "**Exact-payload human approval**",
            "**Idempotency**",
            "**External execution**",
            "**Verification or reconciliation**",
            "**Audit**",
        )
        previous_index = -1
        for step in required_steps:
            with self.subTest(step=step):
                current_index = safety_gate.index(step)
                self.assertGreater(current_index, previous_index)
                previous_index = current_index

    def test_v2_profitability_and_binding_constants_are_documented(self) -> None:
        overview = self.read_document(ARCHITECTURE_DIRECTORY / "overview.md")
        requirements = self.read_document(
            ARCHITECTURE_DIRECTORY / "non-functional-requirements.md"
        )
        profitability = self.read_document(ARCHITECTURE_DIRECTORY / "profitability.md")
        combined = f"{overview}\n{requirements}\n{profitability}"

        self.assert_contains_all(
            profitability,
            (
                "Maroc Affiliate profitability is based on delivered-order economics",
                "Meta-reported conversions and Meta ROAS are informational",
                "delivered revenue",
                "cancellations",
                "returns",
                "COGS",
                "delivery cost",
                "ad spend",
                "net_revenue      = sum(delivered_order_value) - sum(returned_order_value)",
                "true_cost        = ad_spend + (delivered_orders * DELIVERY_COST_PER_ORDER_MAD) + cogs",
                "delivered_roas   = net_revenue / ad_spend",
                "contribution     = net_revenue - true_cost",
                "BREAKEVEN_DELIVERED_ROAS",
                "never hard-coded",
                "DELIVERY_COST_PER_ORDER_MAD",
                "PROFITABILITY_ATTRIBUTION_WINDOW_DAYS",
                "MIN_DAYS_BEFORE_PERFORMANCE_JUDGEMENT",
            ),
        )
        self.assertNotIn("<<SET>>", profitability)
        self.assert_contains_all(
            combined,
            (
                "BUSINESS_CONSTANTS.md",
                "does not invent",
                "startup must fail with a clear configuration error",
                "P05 must not implement a deterministic policy",
                "do not block P00-P04",
            ),
        )

    def test_glossary_delivered_order_roas_matches_binding_economics(self) -> None:
        glossary = self.read_document(ARCHITECTURE_DIRECTORY / "domain-glossary.md")
        glossary_definition = next(
            columns[1].strip()
            for line in glossary.splitlines()
            if line.startswith("|")
            and not line.startswith("| ---")
            and len(columns := line.strip("|").split("|")) == 2
            and columns[0].strip() == "Delivered-order ROAS"
        )

        self.assert_contains_all(
            glossary_definition,
            (
                "net_revenue",
                "delivered_order_value",
                "returned_order_value",
                "delivered_roas",
                "ad_spend",
                "Delivered-order profitability",
            ),
        )
        self.assertRegex(
            glossary_definition,
            r"net_revenue\s*=\s*sum\(delivered_order_value\)\s*-\s*"
            r"sum\(returned_order_value\)",
        )
        self.assertRegex(
            glossary_definition,
            r"delivered_roas\s*=\s*net_revenue\s*/\s*ad_spend",
        )

    def test_v2_meta_launch_risks_start_early_in_parallel_with_engineering(
        self,
    ) -> None:
        requirements = self.read_document(
            ARCHITECTURE_DIRECTORY / "non-functional-requirements.md"
        )
        launch_dependencies = requirements.split(
            "## Meta launch dependencies", maxsplit=1
        )[1].split("## Edge-case expectations", maxsplit=1)[0]

        self.assert_contains_all(
            launch_dependencies,
            (
                "Meta Business verification",
                "Meta App Review",
                "ads_management",
                "ads_read",
                "Meta advertising policy compliance",
                "Review or resubmission delay",
                "beginning in P00 rather than waiting for the Meta-connection phase",
            ),
        )
        self.assertRegex(
            launch_dependencies,
            r"start them early and run them in parallel with\s+engineering",
        )

    def test_markdown_tables_have_matching_header_separator_and_row_columns(
        self,
    ) -> None:
        separator_pattern = re.compile(r"\|(?:\s*:?-{3,}:?\s*\|)+$")

        for document_path in REQUIRED_DOCUMENTS:
            lines = self.read_document(document_path).splitlines()
            for index, header in enumerate(lines[:-1]):
                separator = lines[index + 1]
                if not (
                    header.startswith("|") and separator_pattern.fullmatch(separator)
                ):
                    continue

                expected_columns = header.count("|")
                with self.subTest(
                    document=document_path.name,
                    line=index + 1,
                    kind="separator",
                ):
                    self.assertEqual(expected_columns, separator.count("|"))

                for row_index in range(index + 2, len(lines)):
                    row = lines[row_index]
                    if not row.startswith("|"):
                        break
                    with self.subTest(
                        document=document_path.name,
                        line=row_index + 1,
                        kind="row",
                    ):
                        self.assertEqual(expected_columns, row.count("|"))

    def test_p00_docs_have_no_unresolved_authoring_placeholders(self) -> None:
        unresolved_markers = ("TODO", "TBD", "lorem ipsum", "[insert")
        for document_path in REQUIRED_DOCUMENTS:
            document = self.read_document(document_path).casefold()
            for marker in unresolved_markers:
                with self.subTest(document=document_path.name, marker=marker):
                    self.assertNotIn(marker.casefold(), document)


if __name__ == "__main__":
    unittest.main()
