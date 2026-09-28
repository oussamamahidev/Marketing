# P04 — Identity, Tenant Context, and Authorization

## 1. What We Built

P04 validates signed Maroc Affiliate identities at the entry boundary and turns them into a framework-independent `Principal`. It adds explicit advertising permissions, role mapping, seller context, and a seller-scoped repository lookup convention. No login, password storage, Meta OAuth, database identity tables, or business routes are added.

## 2. Objective

The phase prevents a caller from choosing another seller through a request value. A verified identity supplies one active seller scope, and application helpers pass that scope to every seller-owned lookup.

## 3. Boundary Diagram

```text
Authorization: Bearer JWT
          │
          ▼
core.security verifier ──► Principal ──► application authorization
                                                │
                                                ▼
                                      SellerContext(seller_id)
                                                │
                                                ▼
                             repository.get_for_seller(seller_id, resource_id)
```

## 4. Identity Contract

The default adapter accepts a compact, signed HS256 JWT with `iss`, `aud`, `exp`, `sub`, `seller_id`, `roles`, and `permissions`. `user_id`, when present, must equal `sub`. The platform identity service must issue the active seller membership; no caller-provided seller header, query value, or path component expands scope.

## 5. Configuration

`IDENTITY_JWT_ISSUER`, `IDENTITY_JWT_AUDIENCE`, and `IDENTITY_JWT_HS256_SECRET` are required protected settings. They have no defaults and remain blank in `.env.example`; absent or blank values fail configuration. The secret is a `SecretStr` excluded from representations and model dumps.

## 6. Verification Adapter

`IdentityVerifier` is the narrow port. `HmacSha256IdentityVerifier` is the initial adapter selected by the FastAPI dependency. Replacing it for the platform’s final protocol changes the adapter wiring, not `Principal`, permissions, or application use cases.

## 7. JWT Hardening

The verifier accepts only HS256, verifies an HMAC over the original header and claims segments, checks issuer, audience and expiry, and rejects malformed, duplicate-key, noncanonical-base64url, expired, unknown-role, and unknown-permission inputs. It does not accept an algorithm from the token as configuration.

## 8. Authentication Errors

Missing, malformed, invalid, expired, wrongly issued, wrongly addressed, or incorrectly signed bearer credentials become the canonical `401 UNAUTHENTICATED` envelope. Raw tokens and verifier exception details are never included in a response or log event.

## 9. Principal

`Principal` contains UUID `user_id`, UUID `seller_id`, immutable roles, effective permissions, and `is_platform_admin`. It is constructed only after verification. Roles contribute their mapped permissions; explicitly trusted permission claims can add a known permission.

## 10. Permissions

The vocabulary is `ads.read`, `ads.manage`, `ads.approve`, and `ads.admin`. Viewer, manager, approver, and ads-admin roles map to explicit sets. `ads_admin` maps to the full set; unrelated or misspelled values invalidate the identity.

## 11. Platform Administration

The platform-admin flag is recorded but grants no implicit route permission or cross-seller access. A later, audited administrative feature must declare its own explicit policy and narrow projection before it can use the flag.

## 12. FastAPI Dependencies

`get_authenticated_principal()` performs all token handling. `require_permission(permission)` is a dependency factory, so routes declare their requirement instead of embedding role checks. `get_seller_context()` exposes the verified tenant boundary to use cases.

## 13. Authorization Layer

`authorize()` belongs to the application layer and returns `FORBIDDEN` when an authenticated principal lacks the requested permission. The domain remains independent of FastAPI, headers, and cryptographic parsing.

## 14. Tenant-Scoped Lookup Convention

`SellerScopedLookup` requires `get_for_seller(*, seller_id, resource_id)`. `get_owned_resource()` supplies the verified context’s seller ID and converts a missing result into `RESOURCE_NOT_FOUND`. Future repositories must make the equivalent `WHERE seller_id = :seller_id AND id = :resource_id` predicate part of their boundary.

## 15. IDOR Protection

A foreign resource and a nonexistent resource both produce scoped 404. The lookup never asks a repository to fetch by ID first, so it cannot reveal cross-seller existence or fetch secret-bearing data before scope enforcement.

## 16. Logging and Metrics

Verification is local in this phase and introduces no external call or financially sensitive workflow, so no new metric is needed. Existing structured logging does not allow token text as an event field. Future remote identity adapters need bounded success/failure/latency instrumentation with fixed labels.

## 17. Error Translation

The security adapter raises only a safe internal verification signal. Presentation maps it to the existing application error vocabulary. Authorization denial remains 403, while a seller-scoped absence is 404; these cases are intentionally distinct.

## 18. Cancellation and Dependencies

The initial verifier performs no I/O and has no retry loop. A future remote verifier must use an explicit timeout, preserve cancellation, translate dependency failure without logging credentials, and fail closed rather than treating an ambiguous response as identity.

## 19. Configuration Safety

Template fields, Compose interpolation, default-test fixtures, and container fixtures were all updated together. Test fixtures use a synthetic signing secret only; no deployment value was selected or written to the developer’s `.env`.

## 20. Files and Responsibilities

`core/security.py` verifies signed identities. `domain/identity/principal.py` and `permissions.py` own framework-free identity vocabulary. `application/identity/authorization.py` owns authorization and scoped lookup helpers. `api/dependencies.py` composes them for HTTP.

## 21. Tests

`tests/unit/identity/test_permissions.py` verifies role mapping, permission denial, and scoped lookup arguments. `tests/api/test_authentication.py` covers valid credentials, missing/malformed tokens, signature/algorithm rejection, issuer/audience/expiry failures, 401/403 translation, and secret exclusion. `tests/security/test_tenant_isolation.py` proves cross-seller and missing references fail alike.

## 22. Test Finding

The first adversarial signature test found that a noncanonical base64url final character could decode to unchanged signature bytes. The verifier now re-encodes every segment and requires canonical equality before signature comparison. This rejects ambiguous textual JWT representations.

## 23. Verification Evidence

On 2026-09-22, the supplied formal P04 testing and validation prompts passed: 44 focused identity/permission/tenant tests, 302 default tests, 17 disposable PostgreSQL tests, 3 isolated image tests, Ruff, formatting, and strict mypy. Adversarial testing fixed malformed verifier output and invalid direct seller-context construction; see the P04 validation report.

## 24. Remaining Integration Work

The platform identity owner must provide the production issuer, audience, secure HS256 key distribution or an approved replacement adapter, membership-revocation behavior, and any required service identity contract. Real seller-owned repositories must use the scoped port when their models arrive. P04 does not grant a production admin bypass or implement the later audit trail for one.
