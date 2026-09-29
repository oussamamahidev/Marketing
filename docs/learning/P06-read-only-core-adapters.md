# P06 — Read-Only Core-Service Adapters and Product Context

## 1. What We Built

P06 adds read-only adapters for Catalog, Inventory, Orders, and Content Hub. It maps each internal response to a narrow typed schema, sends seller and service identity on every request, and combines the four results into `ProductAdvertisingContext`.

## 2. Objectives of This Phase

The phase gives later campaign workflows trusted product, stock, order-risk, and creative facts. It does not add writes to Maroc Affiliate services, Meta integration, AI prompts, database tables, or public API routes.

## 3. Files Created

| Area | Responsibility |
|---|---|
| `infrastructure/integrations/common.py` | Bounded GET transport, error translation, metrics, and seller scope checks. |
| `catalog`, `inventory`, `orders`, `content_hub` | Narrow clients and response schemas. |
| `application/context/product_context.py` | Concurrent aggregation through application-owned reader protocols. |
| `tests/contract/internal/` | Mock-transport contract and adversarial tests. |

## 4. Files Modified

`core/config.py` gains optional typed integration settings. `.env.example` documents the base URLs, service identity, timeout, retry limit, and approved Content Hub storage hosts. A client cannot be constructed with incomplete configuration.

## 5. Architecture Explanation

Infrastructure owns HTTP and raw-payload mapping. The application service depends on structural reader protocols, not concrete infrastructure classes. Domain policy remains separate: P06 provides facts; P05 decides whether those facts allow advertising.

## 6. Request / Data Flow

```text
Application use case
    -> ProductAdvertisingContextService
    -> Catalog / Inventory / Orders / Content Hub reader protocols
    -> seller-scoped bounded GET requests
    -> typed schemas
    -> ProductAdvertisingContext
```

## 7. Theory You Need to Understand

An anti-corruption layer prevents external or internal service payloads from becoming application models directly. A narrow schema keeps only information the marketing service needs. A protocol lets application code depend on behavior instead of a concrete HTTP client.

## 8. Practical Implementation Explanation

`ReadOnlyInternalClient` sends only GET requests, sets `X-Seller-ID` and `X-Service-Identity`, disables redirect following, applies the configured timeout, and retries only safe reads up to the configured bound. It maps timeout, unavailable dependency, malformed response, not-found, forbidden, and rate-limit outcomes to stable application errors.

## 9. Important Classes, Functions, Interfaces, and Schemas

- `InternalReadClientConfig` holds an origin, service identity, timeout, and retry limit without exposing the identity in `repr`.
- `ReadOnlyInternalClient.get_json()` is the shared safe transport.
- `CatalogProduct`, `InventorySummary`, `OrderOutcomeSummary`, and `CreativeMetadata` are immutable mapped responses.
- `ProductAdvertisingContextService.get_context()` gathers required facts concurrently and rechecks seller/resource identity.

## 10. Database Changes

None. P06 has no repository implementation, schema migration, transaction, idempotency record, or database write.

## 11. API Changes

None. P06 adds no HTTP route. Existing P04 authentication and authorization continue to protect later API use cases that invoke these readers.

## 12. Security Considerations

Every client read has an explicit seller scope. A returned product or creative with another seller ID becomes a scoped `RESOURCE_NOT_FOUND`, preventing resource disclosure. Content Hub media URLs must be HTTPS, have no credentials or fragments, use the default HTTPS port, and match an approved storage host exactly. The adapter never fetches media URLs itself.

## 13. Error Handling

Timeouts produce `UPSTREAM_TIMEOUT`; connection and server failure produce `DEPENDENCY_UNAVAILABLE`; malformed payloads produce `UPSTREAM_INVALID_RESPONSE`; 404 becomes scoped `RESOURCE_NOT_FOUND`; 401/403 becomes `FORBIDDEN`; and 429 becomes `RATE_LIMITED`. Raw provider messages, payloads, and credentials never cross the boundary.

## 14. Testing Strategy

Contract tests use `httpx2.MockTransport`, which proves the actual request method, headers, paths, retries, response mapping, and failure translation without network access. Tests cover malformed fields, Decimal-safe rates, missing margin, invalid IDs, wrong product IDs, foreign sellers, unsafe URLs, partial aggregation failure, rate limits, identity rejection, and connection/time-out failures.

## 15. Commands Used

```bash
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked mypy src tests
uv run --locked pytest -q
uv run --locked pytest -q tests/security tests/api
uv run --locked pytest -q -m database
uv run --locked pytest -q -m container
```

## 16. How to Test It Manually

Run `uv run --locked pytest -q tests/contract/internal`. Read each contract test as a synthetic internal-service response. A successful request has the caller’s seller ID and service identity headers; a malformed or foreign response raises a controlled `ApplicationError`.

## 17. Design Decisions

The base service URLs are optional settings because deployment endpoints and operational timeout/retry values were not supplied as business constants. Once a client is selected, its factory requires all related values. All aggregation inputs are required because no P05 policy allows an unavailable inventory, order, or creative dependency to be ignored.

## 18. What I Should Learn From This Phase

Never pass an upstream payload directly into business logic. Validate it at the boundary, keep the minimum fields, bind it to tenant scope, and convert technical failures into stable application-level errors.

## 19. Interview Questions From This Phase

1. Why are GET retries acceptable here while write retries are dangerous?
2. Why does a foreign resource return scoped not-found rather than forbidden?
3. How does an approved-host allowlist reduce SSRF risk?
4. Why should the application depend on reader protocols?
5. Why must a partial context not be treated as a valid campaign input?

## 20. Common Mistakes

Do not expose raw internal JSON, follow attacker-controlled media redirects, use a caller-supplied seller ID as authority, retry writes after uncertain outcomes, log service credentials, or allow missing financial inputs to look valid.

## 21. Debugging Guide

Check the stable `ApplicationError.code` first. Then check whether the failure came from transport, HTTP status, schema mapping, tenant scope, or aggregation identity verification. Do not log or copy raw upstream payloads while debugging.

## 22. Connection to Previous Phases

P02 supplies typed configuration and canonical errors. P04 supplies verified seller context and scoped lookup conventions. P05 supplies the deterministic advertising policies that consume the product, inventory, order, and creative facts provided by P06.

## 23. Preparation for the Next Phase

A future application use case must build these clients from protected settings, use verified `SellerContext` rather than client input, and pass the resulting context through P05 policies before it creates a proposal or any external mutation.

## 24. Final Phase Summary

P06 creates a safe read-only integration boundary for core Maroc Affiliate facts. P06 testing found and fixed invalid service origins, service-identity representation exposure, absent margin input, and foreign facts returned by replacement readers. On 2026-09-29, validation passed with 18 focused contract tests, 333 default tests, 81 security/API tests, 17 disposable PostgreSQL tests, isolated Docker regression, Ruff, formatting, and strict mypy.
