<!--
PURPOSE: Record why the MVP does not use RAG or a vector database.
RESPONSIBILITY: Governs MVP knowledge-retrieval scope; it does not prohibit a future evaluated retrieval capability.
DEPENDENCIES: Structured internal service contracts and the P00 AI safety model.
USED BY: AI context design, infrastructure selection, and future product-scope review.
TESTED BY: P00-T ADR review and P00-V acceptance validation.
-->

# ADR-007: Do not use a vector database or RAG in the MVP

**Status:** Accepted — P00 architecture baseline

## Context

The MVP's required context comes from defined, structured, tenant-scoped sources: catalog, inventory, orders, warehouse availability, Content Hub, Meta data, proposals, approvals, and performance snapshots. A vector database or RAG pipeline would add ingestion, ACL filtering, provenance, deletion, reindexing, privacy, prompt-injection, and evaluation concerns without a demonstrated need.

## Decision

Do not introduce RAG or a vector database in the MVP. Build bounded AI context from typed, authorized service calls and PostgreSQL-backed records. Treat all supplied seller text and external content as untrusted, regardless of its source.

## Alternatives considered

| Alternative | Why it was not selected for the MVP |
| --- | --- |
| Managed vector database/RAG from the start | Adds operational and security complexity before an unstructured retrieval need exists. |
| PostgreSQL vector indexing from the start | Still introduces retrieval design and lifecycle obligations that do not support a defined MVP use case. |
| Broad raw-data prompt stuffing | Weakens privacy, context control, provenance, cost, and prompt-injection protections. |

## Consequences

- The MVP has simpler, explicit, tenant-scoped context assembly and fewer data-governance surfaces.
- Semantic search over a large, changing unstructured corpus is not available initially.
- Product requirements that depend on unstructured knowledge must use a typed source or wait for a dedicated retrieval decision.

## Replacement trigger

Add retrieval only when a documented, large, changing unstructured knowledge need cannot be met by structured queries and evaluation demonstrates a material quality, freshness, or usability benefit.

Any retrieval ADR must specify tenant/ACL filtering, provenance and citations where relevant, deletion/reindex lifecycle, privacy/data retention, prompt-injection controls, evaluation, observability, cost limits, and proof that retrieval remains non-authoritative for policy and mutation decisions.
