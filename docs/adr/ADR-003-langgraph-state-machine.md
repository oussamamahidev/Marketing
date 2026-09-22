# ADR-003: Use LangGraph as a controlled state machine

Status: Accepted architecture baseline for MVP.

## Document responsibility

Purpose: constrain AI orchestration and authority. Owns workflow boundaries, not prompts/provider versions or numeric limits. Depends on [project context](../../PROJECT_CONTEXT.md), [business constants](../../BUSINESS_CONSTANTS.md), and [approval ADR](ADR-006-human-approval.md). Used by P10/P11/P17/P18. Tested by P00 review and later graph, injection, schema, approval-resume and AI evaluation tests.

## Context

Proposal generation and campaign analysis need multiple explicit steps, source context, strict outputs and a human approval boundary. An autonomous agent with mutation tools could confuse untrusted text with authority or repeat financially sensitive work after an interruption.

## Decision

Implement bounded LangGraph workflows behind application workflow ports. Use the explicit path: authorized context -> bounded read tools -> structured LLM output -> deterministic validation -> durable human approval -> application-controlled mutation. The graph may interrupt/resume but cannot grant approval or execute an arbitrary Meta write.

Use typed state and strict output schemas, with allowlisted tools and intents. Treat all seller/external content as untrusted data. Resolve provider requests through an LLM abstraction and sanitize context before transport. No OAuth tokens, permission authority or customer PII enter model context.

Apply MAX_GRAPH_STEPS, MAX_STRUCTURED_OUTPUT_RETRIES, LLM_REQUEST_TIMEOUT_SECONDS, token budgets, seller quotas and cost controls from centralized configuration. Exceeding the graph-step cap is a failed run, not an automatic restart. Deterministic truncation must never drop required safety facts silently: missing required context blocks the proposal or diagnosis. Read tools enforce seller scope independently of model-supplied arguments.

Persist resumable state through a PostgreSQL-backed checkpoint adapter isolated from the Domain. Resume rechecks trusted identity, tenant scope, payload version, durable approval and expiry. A replayed checkpoint cannot replay a financial mutation; application execution identity controls that path.

## Alternatives

- Autonomous multi-agent swarm: increases authority/termination complexity without an MVP requirement.
- One unconstrained model call: cannot by itself enforce tool, schema, policy or approval boundaries.
- A handwritten state machine: viable, but would recreate workflow interruption/state tooling; retain the application port so it remains an option.

## Consequences

Flow is explicit and evaluable. LangGraph state/version upgrades and durable checkpoint migrations require care. Model correctness remains probabilistic, so all business authority stays deterministic. AI/provider outage prevents AI generation while manual drafts and permitted non-AI product functions remain available.

## Replacement Trigger

Reconsider the orchestration implementation when required typed-state evolution, interruption/recovery, testability or operational support cannot be maintained safely with the selected LangGraph integration. Demonstrate the limitation with tests or incidents and replace only behind the application port. Durable external business workflows, if later justified, follow ADR-004; changing orchestration never grants the LLM mutation authority.
