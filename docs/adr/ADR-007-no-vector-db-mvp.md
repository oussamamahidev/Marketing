# ADR-007: Do not add RAG or a vector database to the MVP

Status: Accepted architecture baseline for MVP.

## Document responsibility

Purpose: bound context retrieval to the actual product need. Owns the retrieval architecture choice, not commerce schemas or model prompts. Depends on [project context](../../PROJECT_CONTEXT.md), [overview](../architecture/overview.md), and [LangGraph ADR](ADR-003-langgraph-state-machine.md). Used by P06/P10/P17/P18. Tested by P00 scope review and later source-provenance, tenant-isolation, missing-context and AI evaluations.

## Context

The MVP's useful campaign context is structured: selected products/creatives, inventory, orders, seller permissions and performance snapshots. These have authoritative owners and narrow identifiers. There is no specified unstructured knowledge corpus requiring semantic retrieval.

## Decision

Read authorized structured facts through typed integration/repository ports, minimize them into versioned AI context and keep source/provenance references. Use deterministic selection/truncation under configured input limits. Block or explain missing required context rather than retrieving speculative substitutes. Use PostgreSQL for local snapshots and ordinary structured querying.

Do not add RAG pipelines, embedding jobs, vector stores or retrieval-specific packages in MVP. Current stock, budget, permissions, approval and credentials are never determined by semantic retrieval or model memory.

## Alternatives

- A vector database for all context: adds synchronization, tenant filtering, staleness, cost and deletion obligations without solving an established need.
- RAG over product/marketing documents immediately: might help a later knowledge feature, but is not needed for the specified commerce-driven proposal loop.
- Put all platform data into every prompt: violates minimization, token budgets and seller isolation.

## Consequences

Fewer components and clearer provenance reduce MVP operational scope. General unstructured knowledge search is unavailable. Model answers are limited to authorized facts and must disclose insufficient evidence instead of inventing knowledge.

## Replacement Trigger

Revisit only when an approved unstructured-data use case has an identified source owner, permission/deletion rules, freshness requirements and an evaluation showing structured access is insufficient. Compare simpler search first and require measurable retrieval/answer quality plus tenant-isolation tests. A new ADR must describe cost, provenance, deletion and operational ownership. Retrieval would supplement explanation context; it must never replace authoritative safety checks.
