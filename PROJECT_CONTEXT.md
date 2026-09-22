# PROJECT_CONTEXT.md — Binding Context (single source of truth)

Every implementation, testing, and validation prompt in the prompt system depends on this file.
Do not restate this content inside individual prompts. Edit it here only.
Read `BUSINESS_CONSTANTS.md` together with this file — the numeric limits referenced below live there.

You are implementing **Maroc Affiliate AI Marketing Assistant**, an AI-powered Meta advertising subsystem integrated into the existing Maroc Affiliate commerce platform.

Product goal:
- Let sellers connect their Meta advertising account.
- Let sellers choose a Maroc Affiliate product and a creative from the existing Content Hub.
- Let AI generate a safe, structured Meta campaign proposal from product, inventory, order, creative, and seller context.
- Require deterministic business-policy validation and human approval before any financially sensitive action.
- Publish and manage campaigns through a Meta Ads integration gateway that hides MCP/API details from the domain.
- Synchronize ad performance and combine it with real commerce outcomes such as delivered orders, cancellations, returns, margin, stock, and warehouse availability.
- Provide plain-language AI analysis and recommendations.
- Keep the MVP simple and production-oriented.

Architecture baseline:
- Backend: Python + FastAPI.
- Architecture: modular monolith; Presentation -> Application -> Domain <- Infrastructure.
- Database: PostgreSQL.
- ORM/migrations: SQLAlchemy 2.x + Alembic.
- AI orchestration: LangGraph state-machine workflows, not an autonomous agent swarm.
- Background jobs: Celery + Redis for MVP.
- Meta integration: `MetaAdsGateway` interface with MCP/API adapter in Infrastructure.
- LLM: provider abstraction with strict structured outputs.
- Cache/ephemeral coordination: Redis; never source of truth.
- Authentication: existing Maroc Affiliate identity; this service validates/consumes trusted identity and enforces seller tenant scope.
- Authorization: RBAC + ownership checks + selected ABAC policies.
- Observability: structured logs + OpenTelemetry; metrics suitable for Prometheus/Grafana; error tracking.
- Deployment: Docker; managed PostgreSQL and Redis initially.
- Vector DB/RAG: not required for MVP.
- Temporal/Kafka/Kubernetes/microservices: not part of MVP unless a later prompt explicitly introduces them.

Safety invariants:
1. An LLM recommendation is never directly authoritative.
2. Read tools may execute automatically; write tools require authorization, policy validation, exact-payload approval, idempotency, and audit.
3. Seller A must never access Seller B data, tokens, creatives, campaigns, metrics, or approvals.
4. Critical financial mutations fail closed when authoritative persistence is unavailable.
5. No secrets or OAuth tokens may be sent to the LLM or returned to the frontend.
6. External mutations must be idempotent/reconcilable because network timeouts can make results ambiguous.
7. Stock, permissions, budget limits, and approval state must be revalidated immediately before campaign mutation.
8. Do not introduce unrelated architecture or rewrite unrelated files.

## Binding companions
- `BUSINESS_CONSTANTS.md` — all numeric thresholds, currency, limits, and objectives. Any prompt saying "configured maximum", "threshold", or "limit" resolves against that file.
- `docs/architecture/domain-glossary.md` — canonical terms (produced by P00).
