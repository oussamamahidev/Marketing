"""P00 document contracts, including deliberately corrupted in-memory inputs.

These tests validate specifications, not future runtime policies or services.
Business values are read from BUSINESS_CONSTANTS.md; none are copied here.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

import pytest

ROOT = Path(__file__).resolve().parents[1]
ARCH = ROOT / "docs" / "architecture"
ADR = ROOT / "docs" / "adr"
ADR_NAMES = (
    "ADR-001-modular-monolith.md",
    "ADR-002-postgresql.md",
    "ADR-003-langgraph-state-machine.md",
    "ADR-004-celery-before-temporal.md",
    "ADR-005-meta-gateway-abstraction.md",
    "ADR-006-human-approval.md",
    "ADR-007-no-vector-db-mvp.md",
)
ARCH_NAMES = (
    "overview.md",
    "domain-glossary.md",
    "non-functional-requirements.md",
    "profitability.md",
)
NUMERIC_NAMES = frozenset(
    """
MIN_DAILY_BUDGET_MAD MAX_DAILY_BUDGET_MAD MAX_DAILY_BUDGET_PER_SELLER_MAD
MAX_BUDGET_INCREASE_PCT_PER_ACTION MIN_HOURS_BETWEEN_BUDGET_CHANGES
MIN_STOCK_UNITS_TO_ADVERTISE STOCK_FLOOR_TO_AUTO_PAUSE MIN_GROSS_MARGIN_PCT
MAX_ACCEPTABLE_CANCELLATION_RATE_PCT MAX_ACCEPTABLE_RETURN_RATE_PCT
MIN_ORDERS_FOR_RATE_CONFIDENCE DELIVERY_COST_PER_ORDER_MAD
PROFITABILITY_ATTRIBUTION_WINDOW_DAYS MIN_DAYS_BEFORE_PERFORMANCE_JUDGEMENT
MAX_GRAPH_STEPS MAX_STRUCTURED_OUTPUT_RETRIES LLM_REQUEST_TIMEOUT_SECONDS
MAX_INPUT_TOKENS_PER_RUN MAX_OUTPUT_TOKENS_PER_RUN
MAX_AI_PROPOSALS_PER_SELLER_PER_DAY MAX_LLM_COST_PER_SELLER_PER_DAY_MAD
MAX_SELLER_INSTRUCTION_CHARS IDEMPOTENCY_KEY_TTL_HOURS META_WRITE_TIMEOUT_SECONDS
MAX_RETRIES_META_WRITE EXECUTING_STATE_STALE_AFTER_MINUTES
RECONCILIATION_SCAN_INTERVAL_MINUTES APPROVAL_PAYLOAD_TTL_MINUTES
PERFORMANCE_SYNC_INTERVAL_MINUTES PERFORMANCE_SNAPSHOT_RETENTION_DAYS
META_API_RATE_LIMIT_BUFFER_PCT SYNC_BACKFILL_MAX_DAYS DEFAULT_PAGE_SIZE
MAX_PAGE_SIZE RATE_LIMIT_AUTHENTICATED_PER_MINUTE RATE_LIMIT_AI_ENDPOINTS_PER_MINUTE
SSE_MAX_STREAM_DURATION_SECONDS RTO_MINUTES RPO_MINUTES BACKUP_RETENTION_DAYS
RESTORE_TEST_FREQUENCY_DAYS
""".split()
)
FIXED_VALUES = {
    "PLATFORM_CURRENCY": "MAD",
    "MONEY_STORAGE": "integer centimes",
    "META_ACCOUNT_CURRENCY_POLICY": "reject mismatch",
    "FX_CONVERSION": "not supported in MVP",
    "BUDGET_CHANGE_REQUIRES_APPROVAL": "true",
    "BREAKEVEN_DELIVERED_ROAS": "computed",
}
NONNEGATIVE_NAMES = {
    "MAX_STRUCTURED_OUTPUT_RETRIES",
    "MAX_RETRIES_META_WRITE",
    "DELIVERY_COST_PER_ORDER_MAD",
    "MAX_LLM_COST_PER_SELLER_PER_DAY_MAD",
}


def markdown_table(document: str, first_header: str) -> list[list[str]]:
    """Read a simple Markdown table by its first header cell; reject bad rows."""
    lines = document.splitlines()
    for index, line in enumerate(lines):
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if not line.startswith("|") or cells[0] != first_header:
            continue
        rows = []
        for row in lines[index + 2 :]:
            if not row.startswith("|"):
                break
            values = [cell.strip() for cell in row.strip().strip("|").split("|")]
            if len(values) != len(cells):
                raise ValueError(f"malformed table row: {row}")
            rows.append(values)
        if not rows:
            raise ValueError(f"empty table: {first_header}")
        return rows
    raise ValueError(f"missing table: {first_header}")


def constants(document: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in document.splitlines():
        if not line.startswith("| `"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != 3:
            raise ValueError("malformed constant row")
        identifier = cells[0].strip("`")
        if not re.fullmatch(r"[A-Z][A-Z0-9_]+", identifier):
            raise ValueError("invalid constant identifier")
        if identifier in values:
            raise ValueError(f"duplicate constant: {identifier}")
        values[identifier] = cells[1].strip("`")
    expected = NUMERIC_NAMES | FIXED_VALUES.keys()
    if values.keys() != expected:
        raise ValueError(f"constant names differ: {values.keys() ^ expected}")
    for name in NUMERIC_NAMES:
        if not re.fullmatch(r"\d+", values[name]):
            raise ValueError(f"missing or invalid numeric constant: {name}")
        if int(values[name]) < (0 if name in NONNEGATIVE_NAMES else 1):
            raise ValueError(f"out-of-range constant: {name}")
        if "_PCT" in name and int(values[name]) > 100:
            raise ValueError(f"invalid percentage: {name}")
    for name, value in FIXED_VALUES.items():
        if values[name] != value:
            raise ValueError(f"fixed invariant changed: {name}")
    for lower, upper in (
        ("MIN_DAILY_BUDGET_MAD", "MAX_DAILY_BUDGET_MAD"),
        ("MAX_DAILY_BUDGET_MAD", "MAX_DAILY_BUDGET_PER_SELLER_MAD"),
        ("DEFAULT_PAGE_SIZE", "MAX_PAGE_SIZE"),
    ):
        if int(values[lower]) > int(values[upper]):
            raise ValueError(f"inverted bounds: {lower}, {upper}")
    if int(values["STOCK_FLOOR_TO_AUTO_PAUSE"]) >= int(values["MIN_STOCK_UNITS_TO_ADVERTISE"]):
        raise ValueError("stock pause floor must be below creation threshold")
    return values


def section(document: str, heading: str) -> str:
    matches = [
        match.group(1)
        for match in re.finditer(
            rf"^## {re.escape(heading)}\n(.*?)(?=^## |\Z)",
            document,
            re.M | re.S,
        )
    ]
    if len(matches) != 1 or not matches[0].strip():
        raise ValueError(f"missing, duplicate or empty section: {heading}")
    return matches[0]


def proposal_graph(document: str) -> dict[str, set[str]]:
    graph: dict[str, set[str]] = {}
    for source, targets, _ in markdown_table(document, "Proposal state"):
        sources = re.findall(r"`([A-Z_]+)`", source)
        if not sources:
            raise ValueError("missing state identifier")
        destinations = set(re.findall(r"`([A-Z_]+)`", targets))
        if not destinations and "Terminal" not in targets:
            raise ValueError("missing transition identifier")
        for state in sources:
            if state in graph:
                raise ValueError(f"duplicate state: {state}")
            graph[state] = destinations
    if any(target not in graph for targets in graph.values() for target in targets):
        raise ValueError("undefined transition target")
    return graph


def validate_proposal_graph(graph: dict[str, set[str]]) -> None:
    if graph.get("PUBLISHED") != set() or graph.get("CANCELLED") != set():
        raise ValueError("terminal state has outgoing transitions")
    for required_gate in ("VALIDATING", "AWAITING_APPROVAL", "APPROVED"):
        pending = ["DRAFT"]
        visited = {required_gate}
        while pending:
            state = pending.pop()
            if state in visited:
                continue
            if state in {"EXECUTION_PENDING", "PUBLISHED"}:
                raise ValueError(f"path bypasses {required_gate}")
            visited.add(state)
            pending.extend(graph[state] - visited)
    if "CANCELLED" not in graph["EXECUTION_PENDING"]:
        raise ValueError("pre-dispatch cancellation leaves proposal pending")


def check_links(path: Path) -> None:
    # Current documentation uses inline links; code blocks are not link markup.
    document = re.sub(r"^```.*?^```[^\n]*", "", path.read_text(), flags=re.M | re.S)
    for destination in re.findall(r"\[[^\]]+\]\(([^)]+)\)", document):
        parsed = urlsplit(destination)
        if parsed.scheme or parsed.netloc:
            continue
        target = path.parent / unquote(parsed.path) if parsed.path else path
        if not target.is_file():
            raise ValueError(f"broken link in {path.name}: {destination}")
        if parsed.fragment:
            headings = re.findall(r"^#+\s+(.+)$", target.read_text(), re.M)
            anchors = {re.sub(r"[^\w\- ]", "", h.lower()).replace(" ", "-") for h in headings}
            if unquote(parsed.fragment) not in anchors:
                raise ValueError(f"missing anchor: {destination}")


def replace_constant(document: str, name: str, value: str) -> str:
    return re.sub(rf"^(\| `{name}` \| )[^|]+", rf"\g<1>{value} ", document, flags=re.M)


@pytest.fixture
def constant_document() -> str:
    return (ROOT / "BUSINESS_CONSTANTS.md").read_text()


@pytest.mark.parametrize("name", ARCH_NAMES)
def test_required_architecture_documents(name: str) -> None:
    document = (ARCH / name).read_text()
    assert section(document, "Document responsibility")
    assert len(re.findall(r"^```", document, re.M)) % 2 == 0


@pytest.mark.parametrize("name", ADR_NAMES)
def test_adr_sections_are_unique_and_nonempty(name: str) -> None:
    document = (ADR / name).read_text()
    for heading in ("Context", "Decision", "Alternatives", "Consequences", "Replacement Trigger"):
        assert section(document, heading)


@pytest.mark.parametrize(
    "bad", ["", "## Decision\n\n## Context\ntext", "## Decision\na\n## Decision\nb"]
)
def test_section_checker_rejects_missing_empty_or_duplicate_sections(bad: str) -> None:
    with pytest.raises(ValueError, match="section"):
        section(bad, "Decision")


def test_all_document_links_resolve() -> None:
    paths = list((ROOT / "docs").rglob("*.md"))
    paths += [ROOT / "PROJECT_CONTEXT.md", ROOT / "BUSINESS_CONSTANTS.md"]
    if (ROOT / "README.md").exists():
        paths.append(ROOT / "README.md")
    for path in paths:
        check_links(path)


@pytest.mark.parametrize("destination", ["missing.md", "target.md#missing"])
def test_link_checker_rejects_broken_file_or_anchor(tmp_path: Path, destination: str) -> None:
    (tmp_path / "target.md").write_text("# Present\n")
    source = tmp_path / "source.md"
    source.write_text(f"[link]({destination})")
    with pytest.raises(ValueError):
        check_links(source)


def test_link_checker_accepts_relative_files_and_anchors(tmp_path: Path) -> None:
    (tmp_path / "target file.md").write_text("# Valid heading\n")
    source = tmp_path / "source.md"
    source.write_text("[link](target%20file.md#valid-heading)")
    check_links(source)


def test_business_constants_complete_and_consistent(constant_document: str) -> None:
    constants(constant_document)
    assert "<<SET>>" not in constant_document


@pytest.mark.parametrize("invalid", ["", "`<<SET>>`", "`nan`", "`true`", "`-1`", "`1.5`"])
def test_reject_missing_or_malformed_numeric_value(constant_document: str, invalid: str) -> None:
    with pytest.raises(ValueError, match="numeric constant"):
        constants(replace_constant(constant_document, "MAX_DAILY_BUDGET_MAD", invalid))


@pytest.mark.parametrize(
    "mutation", ["missing", "duplicate", "invalid_name", "unknown_name", "bad_row"]
)
def test_reject_invalid_constant_schema(constant_document: str, mutation: str) -> None:
    row = next(
        line
        for line in constant_document.splitlines()
        if line.startswith("| `MAX_DAILY_BUDGET_MAD` |")
    )
    replacement = {
        "missing": "",
        "duplicate": row + "\n" + row,
        "invalid_name": row.replace("MAX_DAILY_BUDGET_MAD", "bad-name"),
        "unknown_name": row.replace("MAX_DAILY_BUDGET_MAD", "MAX_UNKNOWN_BUDGET_MAD"),
        "bad_row": row + " extra |",
    }[mutation]
    with pytest.raises(ValueError):
        constants(constant_document.replace(row, replacement))


def test_approval_cannot_be_disabled(constant_document: str) -> None:
    with pytest.raises(ValueError, match="fixed invariant"):
        constants(replace_constant(constant_document, "BUDGET_CHANGE_REQUIRES_APPROVAL", "false"))


@pytest.mark.parametrize(
    "lower,upper",
    [
        ("MIN_DAILY_BUDGET_MAD", "MAX_DAILY_BUDGET_MAD"),
        ("MAX_DAILY_BUDGET_MAD", "MAX_DAILY_BUDGET_PER_SELLER_MAD"),
        ("DEFAULT_PAGE_SIZE", "MAX_PAGE_SIZE"),
    ],
)
@pytest.mark.parametrize("offset", [-1, 0, 1])
def test_configuration_ordering_boundaries(
    constant_document: str,
    lower: str,
    upper: str,
    offset: int,
) -> None:
    boundary = int(constants(constant_document)[upper])
    changed = replace_constant(constant_document, lower, str(boundary + offset))
    if offset > 0:
        with pytest.raises(ValueError, match="inverted bounds"):
            constants(changed)
    else:
        constants(changed)


def test_zero_allowed_only_for_nonnegative_settings(constant_document: str) -> None:
    for name in NUMERIC_NAMES:
        changed = replace_constant(constant_document, name, "0")
        if name in NONNEGATIVE_NAMES:
            constants(changed)
        else:
            with pytest.raises(ValueError, match="out-of-range"):
                constants(changed)


@pytest.mark.parametrize("offset", [-1, 0, 1])
def test_stock_threshold_ordering_boundary(constant_document: str, offset: int) -> None:
    boundary = int(constants(constant_document)["MIN_STOCK_UNITS_TO_ADVERTISE"])
    changed = replace_constant(
        constant_document, "STOCK_FLOOR_TO_AUTO_PAUSE", str(boundary + offset)
    )
    if offset >= 0:
        with pytest.raises(ValueError, match="stock pause floor"):
            constants(changed)
    else:
        constants(changed)


def test_documented_constant_references_exist(constant_document: str) -> None:
    names = constants(constant_document)
    error_rows = markdown_table(
        (ARCH / "non-functional-requirements.md").read_text(), "HTTP/status"
    )
    error_codes = {code for row in error_rows for code in re.findall(r"`([A-Z_]+)`", row[1])}
    prefixes = {name.split("_")[0] for name in names if "_" in name}
    pattern = r"\b(?:" + "|".join(sorted(prefixes)) + r")_[A-Z][A-Z_0-9]+\b"
    for path in (ROOT / "docs").rglob("*.md"):
        references = set(re.findall(pattern, path.read_text()))
        # Declared error/status codes share prefixes but are not configuration.
        assert references <= names.keys() | error_codes, (
            path,
            references - names.keys() - error_codes,
        )


def test_proposal_state_graph_has_no_approval_bypass_and_handles_cancellation() -> None:
    validate_proposal_graph(proposal_graph((ARCH / "overview.md").read_text()))


@pytest.mark.parametrize(
    "mutation",
    [
        "approval_bypass",
        "validation_bypass",
        "review_bypass",
        "terminal_reopen",
        "cancel_gap",
    ],
)
def test_state_checker_rejects_unsafe_transitions(mutation: str) -> None:
    graph = proposal_graph((ARCH / "overview.md").read_text())
    if mutation == "approval_bypass":
        graph["DRAFT"].add("EXECUTION_PENDING")
    elif mutation == "validation_bypass":
        graph["DRAFT"].add("AWAITING_APPROVAL")
    elif mutation == "review_bypass":
        graph["VALIDATING"].add("APPROVED")
    elif mutation == "terminal_reopen":
        graph["PUBLISHED"].add("DRAFT")
    else:
        graph["EXECUTION_PENDING"].discard("CANCELLED")
    with pytest.raises(ValueError):
        validate_proposal_graph(graph)


def test_state_checker_rejects_undefined_target() -> None:
    changed = (
        (ARCH / "overview.md")
        .read_text()
        .replace(
            "| `DRAFT` | `VALIDATING`, `CANCELLED` |",
            "| `DRAFT` | `NONEXISTENT_STATE`, `CANCELLED` |",
        )
    )
    with pytest.raises(ValueError, match="undefined"):
        proposal_graph(changed)


def test_profitability_expressions_match_binding_formula(constant_document: str) -> None:
    root_code = re.findall(r"```\n(.*?)\n```", constant_document, re.S)[0]
    model_code = re.findall(r"```text\n(.*?)\n```", (ARCH / "profitability.md").read_text(), re.S)[
        0
    ]
    # Normalize the documented exact unit conversion and named intermediate.
    model_code = model_code.replace(
        "configured_delivery_cost_centimes", "DELIVERY_COST_PER_ORDER_MAD"
    )

    def assignments(code: str) -> dict[str, ast.expr]:
        result: dict[str, ast.expr] = {}
        for node in ast.parse(code).body:
            assert isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)
            result[node.targets[0].id] = node.value
        return result

    reference, described = assignments(root_code), assignments(model_code)

    class ExpandDeliveryCost(ast.NodeTransformer):
        def visit_Name(self, node: ast.Name) -> ast.expr:
            return described["delivery_cost"] if node.id == "delivery_cost" else node

    for name, expected in reference.items():
        actual = ExpandDeliveryCost().visit(described[name])
        assert ast.dump(actual) == ast.dump(expected), name
