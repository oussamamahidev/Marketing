# P00 testing and validation

```text
Implementation: PASS
Unit Tests: PASS
Integration Tests: PASS
Security: PASS
Architecture: PASS
Regression: PASS
Overall: PASS
```

Review date: 2026-09-20. The supplied TESTING PROMPT P00 and VALIDATION PROMPT P00 have now been applied. PASS covers the P00 documentation baseline and its executable documentation checks. Integration Tests PASS means the applicability review passed: P00 contains no runtime integration to exercise. It does not claim a database, Redis, Meta, LLM or API test was executed.

## Document responsibility

This report owns P00 test evidence, review findings, category applicability and the next-phase gate. It does not introduce product functionality or certify future runtime behavior. It depends on the root [project context](../../PROJECT_CONTEXT.md), [business constants](../../BUSINESS_CONSTANTS.md), the supplied P00 implementation/testing/validation prompts and the documents below. Used by the project owner and P01 implementer. Verified by [P00 document tests](../../tests/test_p00_documentation.py), lint, strict type checking and manual architecture/security review.

## Commands and evidence

No pyproject, configured test markers, application source or previous test suite existed before this step. Commands were adapted to the actual documentation-only repository rather than creating the P01 toolchain.

| Command | Result | Meaning |
|---|---|---|
| `pytest -q` | PASS: 53 passed; no skips or warnings | Entire available suite, including document checks and corrupted-input cases |
| `mypy --strict --cache-dir /tmp/codex-p00-mypy-cache tests` | PASS: no issues in the test module | Tests are the only Python source; there is no `src` directory to type-check |
| `ruff check .` | UNAVAILABLE: command not found | Ruff was not installed; this is not recorded as a Ruff pass |
| `uv tool run --cache-dir /tmp/codex-p00-uv-cache --isolated ruff --version` | Download failed | Initial sandbox DNS failure; approved retry reached package resolution but the wheel download timed out. No project dependencies were changed |
| `flake8 --select E4,E7,E9,F .` | PASS | Available adapted lint check using the same rule families as Ruff's default selection; not a claim that the tools have identical implementations |

The testing prompt allows adapting commands. With no existing project toolchain, the installed Flake8 check provides the applicable lint gate, alongside strict mypy and pytest. P01 remains responsible for selecting, pinning and configuring the permanent quality tools, including Ruff. No network calls or service credentials are required to run the document tests.

## Tests and negative evidence

The suite verifies all requested architecture files, unique/nonempty ADR decision sections, local Markdown file links and heading anchors, complete/typed business-constant rows, fixed safety invariants, named constant references, configuration ordering, proposal-state reachability, terminal states, cancellation mapping, and structural equality of the profitability expressions with the binding formula after normalizing the named delivery-cost intermediate/unit conversion.

Corrupted in-memory inputs prove rejection of missing/empty/duplicate ADR sections, nonexistent files and anchors, missing/duplicate/unknown/malformed constant identifiers and rows, unresolved/empty/non-numeric/negative values, disabled approval, inverted budget/page limits, invalid stock-threshold relationships, undefined state targets, reopened terminal states, omitted cancellation, and paths bypassing validation, human review or approval. Temporary files exercise the link checker; the suite does not modify the project documents while testing them.

Boundary checks derive values from named constants and exercise below/equal/above ordering boundaries for budget, page sizes and stock thresholds. Zero-value checks distinguish positive requirements from nonnegative settings. These validate configuration-document consistency; they do not pretend to test runtime budget acceptance, rate limiting or inventory policies before those exist. No configured business values were copied into test fixtures.

## Defect found and corrected

| Item | Evidence |
|---|---|
| Problem | A confirmed pre-dispatch execution cancellation left its proposal in EXECUTION_PENDING with no documented transition to CANCELLED |
| File | [Overview: proposal lifecycle](overview.md) |
| Root cause | The execution lifecycle allowed cancellation, but the proposal transition table listed only publication/failure outcomes |
| Fix | Add CANCELLED as a permitted outcome of EXECUTION_PENDING only for confirmed pre-dispatch cancellation, updating execution and proposal in the same transaction |
| Regression proof | `test_proposal_state_graph_has_no_approval_bypass_and_handles_cancellation` failed before the fix and passes afterward; the `cancel_gap` mutation proves the checker still detects removal of the transition |

The initial test run also identified a test-checker false positive: documented error/status codes were treated as undeclared business constants because they share prefixes. The checker now recognizes codes declared in the canonical error table; unknown configuration references still fail. Strict type checking found an untyped regular-expression return in the new test helper, which was corrected before the final suite. No prior tests were removed or weakened, and no production code was added or changed.

## Required test category applicability

| Category | Applicability and evidence |
|---|---|
| Unit tests | Applicable to documentation parsing/validation helpers; exercised against repository documents and invalid synthetic inputs. Pure domain/application runtime tests do not apply because no such code exists |
| Documentation consistency | Applicable and passed: required files/ADR sections, constant schema/references/relationships, proposal graph and profitability expressions; manual semantic review complements structural tests |
| Broken links | Applicable and passed using a local filesystem/anchor checker whose own negative cases prove broken links fail. External provider availability is not a P00 link contract |
| Invalid/missing identifiers and malformed schemas | Applicable to documented constant identifiers/rows and state targets; negative tests pass. API payload schema execution is deferred because no endpoint or application schema exists |
| Invalid state transitions | Applicable to the documented proposal graph: publication/execution cannot bypass required gates and terminal states cannot reopen. Runtime transition enforcement belongs to P05/P11/P12 |
| Missing required configuration | Applicable to BUSINESS_CONSTANTS: missing/unresolved/invalid entries and disabled approval are rejected by document checks. Startup failure enforcement belongs to P02 because no config loader exists yet |
| Empty/min/max and daily budget/page boundaries | Applicable to configuration ordering and required positive/nonnegative values, with values derived from named constants. Actual daily-budget acceptance and page slicing are not executable in P00; P05/P14 own them |
| Oversized seller instructions/text | Runtime test does not apply: no instruction-input handler or LLM workflow exists. MAX_SELLER_INSTRUCTION_CHARS is resolved, referenced, and NFRs require rejection; P10/P18 test the actual boundary |
| Permission/tenant/admin tests | Security-design review applies and passed: trusted seller context, scoped queries, explicit admin permissions and safe 401/403/404 semantics are documented. HTTP response and cross-tenant DB execution tests do not apply until P04 and later APIs/repositories exist |
| Failure simulations | Runtime simulation does not apply because P00 calls no dependencies. Manual review verifies specified safe handling of timeout, connection loss, malformed response, throttling, expired credentials and partial success; NFRs assign implementation tests to the owning phases |
| Concurrency/idempotency/transactions | Design review applies: PostgreSQL claims, approval consumption, reservation, audit/intent, duplicate-key conflict and reconciliation-before-retry are explicit. There is no state-mutating implementation or database constraint to race-test in P00; P12/P13 must use real PostgreSQL |
| Database/migration tests | Not applicable to execution: no repositories, schema or migrations exist. Starting disposable PostgreSQL would exercise none of the files under test. P03 onward must test actual database behavior with a real disposable instance |
| Redis/Celery tests | Not applicable to execution: neither client, task nor worker exists. P15 must exercise the real queue/Redis behavior as required; no substitute mock is claimed here |
| LLM/Meta/internal-service contract mocks | Not applicable: only interface designs exist; no adapters or wire schemas are implemented. P06/P08/P10 introduce contract fixtures and interface-level fakes |
| Security misuse | Documentation and approval-bypass graph checks apply; no network penetration or live-account actions are justified for this documentation task. Runtime token leakage, prompt injection, SSRF and tenant attack tests remain mandatory in their implementation phases |
| Regression suites | Entire current suite passed; no earlier executable suite existed. Root context and finalized business values remain unchanged in this step, and the required architecture/ADR/link checks cover affected documents |
| Coverage | No critical domain/security/idempotency runtime branches exist to measure. No application coverage percentage is claimed. Invalid document inputs and graph bypasses are exercised without adding skipped placeholder tests |

## Validation review

| Review area | Finding and evidence |
|---|---|
| Implementation correctness | [Overview](overview.md) supplies scope, actors, use cases, MUST/SHOULD/NICE/OUT-OF-SCOPE priorities, integration ownership, narrow ports, layer dependencies and P01 handoff. Constants are resolved and their assumptions remain explicit |
| Unit tests | Complete available suite passes, including negative checker cases and the demonstrated cancellation regression |
| Integration/contract/API | No implementation exists in P00; non-applicability is justified above, not hidden behind skipped tests. Future real-service/DB testing remains explicitly assigned |
| Architecture/dependencies | Domain is framework-independent; Application owns orchestration/transactions; Infrastructure implements ports; routes/workers remain thin. PostgreSQL is local authority, Redis ephemeral, and LangGraph bounded behind a port |
| Authentication/authorization/tenant isolation | [NFRs](non-functional-requirements.md) require trusted memberships, action permissions, ownership, seller-scoped lookups, explicit admin capabilities, safe not-found semantics and tenant-bound credential resolution |
| Security/secrets | No token or credential data is added. Docs prohibit secrets/PII in model context and logs, treat seller/provider data as untrusted, allowlist read tools, require exact approval and fail closed on unavailable safety facts |
| Idempotency/concurrency/transactions | Approved payload, consumed approval, durable execution, budget claim and audit/dispatch intent are tied transactionally. Same-key changed-payload requests conflict; ambiguous external effects retain reservations and require reconciliation |
| Failure/external ambiguity | Known failure differs from unknown outcome; partial writes, cancellation after send, timeout and after-send commit failures cannot be treated as a safe retry or fictitious rollback |
| Logging/metrics/observability | Structured correlation and secret-redaction requirements are explicit; metric labels are bounded. P00 adds no operational behavior requiring runtime instrumentation |
| Performance | No runtime queries, endpoints or workers exist, so N+1/full-scan execution analysis is not applicable. ADR-002 requires bounded analytics and measured tuning before adding specialized storage; no invented performance guarantees |
| Documentation/migrations | Required files and links pass checks; glossary defines requested terms; profitability preserves the binding formula and informational Meta-conversion label. No migration exists or is needed for this documentation correction |
| Regression risk | Change is confined to a missing documentation transition, gate/report updates and document tests. No production code, CI, migration or dependency manifest was introduced |

## Acceptance criteria and gate

- Every ADR has nonempty Context, Decision, Alternatives, Consequences and Replacement Trigger sections.
- No MVP requirement depends on Kafka, Kubernetes, microservices, RAG, vector storage or Temporal. These are excluded or conditional future decisions.
- Financially sensitive operations explicitly require deterministic policy validation, exact-payload human approval, idempotency and audit; the LLM never gains authority.
- Another engineer can implement P01 from the explicit layer/layout/ownership decisions without inventing architecture. Package/tool version selection is appropriately left to P01.

P00 implementation, testing and validation pass for their documentation scope. **P01 may begin.** This task does not implement P01. The pre-production review of MVP assumptions, Meta verification/App Review and the named identity/commerce/provider contracts remain later-phase or launch dependencies; none is represented as already fulfilled.
