<!--
PURPOSE: Record the controlled workflow model for AI-assisted proposal and analysis work.
RESPONSIBILITY: Governs AI orchestration boundaries; it does not grant an LLM policy or mutation authority.
DEPENDENCIES: P00 architecture overview, deterministic domain policies, and LLM provider contracts.
USED BY: Proposal generation, analysis, approval interrupt/resume, and AI evaluation work.
TESTED BY: P00-T ADR review and later workflow/security/AI evaluation tests.
-->

# ADR-003: Use LangGraph as a controlled state machine

**Status:** Accepted — P00 architecture baseline

## Context

Campaign proposal generation and analysis need explicit steps for authorized context gathering, structured LLM output, deterministic validation, state inspection, and pause/resume around seller approval. A free-form autonomous agent could misuse tools, blur responsibilities, make non-repeatable decisions, or bypass business policy.

## Decision

Use LangGraph as a typed, controlled state-machine workflow. It receives only authorized, tenant-scoped, sanitized context; uses only explicitly registered read tools; and returns strict structured output.

Deterministic policy validation, seller approval, idempotency creation, audit persistence, and Meta mutations remain application/domain-controlled operations. An LLM cannot directly call a write-capable tool or decide permission, budget, stock, approval, or external mutation state.

## Alternatives considered

| Alternative | Why it was not selected for the MVP |
| --- | --- |
| Autonomous agent swarm | Has unclear authority, tool boundaries, repeatability, and auditability for financially sensitive work. |
| Linear prompt chain | Provides weaker explicit state, branching, interruption, and recovery semantics. |
| Custom workflow engine | Adds substantial build and maintenance cost before LangGraph's controlled graph model is shown insufficient. |

## Consequences

- Workflow nodes, transitions, schemas, prompts, and tool permissions are explicit and testable.
- Proposal generation can pause for approval without treating approval as an LLM decision.
- The team must version schemas/prompts/graphs, record safe workflow evidence, and observe failure and invalid-output paths.
- LangGraph coordinates work; PostgreSQL-backed application state remains authoritative for approvals and executions.

## Replacement trigger

Replace or supplement LangGraph only if measured evaluation or production evidence shows that it cannot meet required typed state control, interruption/resumption, auditability, security controls, or operational reliability.

Any replacement must preserve every deterministic safety gate and be assessed by a new ADR. A free-form autonomous agent is not an acceptable replacement for this workflow.
