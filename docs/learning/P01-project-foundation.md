# P01 — Repository Foundation and Python Quality Toolchain

## 1. What We Built

P01 turns P00's architecture documents into an installable, runnable Python project. The application is deliberately small: `create_app()` constructs FastAPI and exposes its default documentation endpoints. There are no advertising operations yet.

Before P01, the repository held context, business constants, architecture decisions and document tests. After P01, a developer can install a locked environment, import the package outside the source directory, start an HTTP server, run quality checks, and build an isolated non-root container. Compose supplies optional local PostgreSQL and Redis infrastructure; the app does not connect to either.

```text
P00 architecture and document tests
             ↓
P01 package + app factory + tooling + Docker/Compose
             ↓
Reproducible installation, startup and verification
             ↓
Foundation consumed by subsequent implementation phases
```

This document describes P01's implementation and completed testing. Later business behavior is not represented as already implemented.

## 2. Objectives of This Phase

| Category | Requirement | Implementation | Why it matters |
|---|---|---|---|
| Functional | Import and start the application | Installed src-layout package and `create_app()` | Establishes a real executable entrypoint |
| Architecture | Preserve the agreed boundaries | Factory contains no business rules or integrations | Later layers can be introduced without untangling an oversized entrypoint |
| Security | Exclude secrets and run without root | Ignore rules, blank example password, explicit image inputs, non-root runtime | Reduces accidental credential distribution and process privileges |
| Reliability | Repeat dependency resolution | Constrained dependencies, `uv.lock`, locked installation and digest-pinned build images | Prevents an unnoticed dependency change on every installation |
| Testing | Enforce quality and preserve P00 | Ruff, strict mypy, pytest, import/API/configuration checks and real container tests | Catches packaging and operational failures before domain work begins |

The foundation does not implement seller permissions, financial rules, secret storage or service health probes. Those objectives remain outside P01.

## 3. Files Created

The table covers the full P01 implementation and its testing/documentation follow-up. A file created in implementation may also appear in the modifications table when testing refined it.

| File | Purpose | Layer | Used By |
|---|---|---|---|
| `pyproject.toml` | Package metadata, dependencies, build backend and quality configuration | Development/build | uv, Ruff, mypy, pytest |
| `uv.lock` | Resolved versions and artifact hashes | Development/build | Locked local and image installs |
| `.env.example` | Safe local Compose input template | Local operations | Developer setup |
| `.gitignore` | Keep local secrets and generated files out of ordinary Git additions | Repository | Git |
| `.dockerignore` | Allow only package inputs into build context | Build security | Docker builder |
| `Dockerfile` | Build/install runtime package and start Uvicorn as non-root | Deployment foundation | Docker |
| `docker-compose.yml` | Local PostgreSQL, Redis and optional app service | Local operations | Docker Compose |
| `src/marketing_ai/__init__.py` | Define importable package without service I/O | Package | Python import system |
| `src/marketing_ai/main.py` | Construct the FastAPI application | Composition/presentation | Uvicorn and test fixtures |
| `tests/conftest.py` | App, async backend and in-process HTTP fixtures | Tests | API/startup tests |
| `tests/unit/test_imports.py` | Import, construction and minimal HTTP checks | Tests | Default pytest suite |
| `tests/unit/test_foundation.py` | Real Git/uv/Compose configuration checks | Tests | Default pytest suite |
| `tests/integration/test_container.py` | Actual Docker build/runtime/context checks | Tests | Explicit container suite |
| `README.md` | Exact setup, run and verification instructions | Documentation | Developers |
| `docs/architecture/p01-validation.md` | Review evidence, applicability and completion gate | Documentation | Reviewers and next-phase implementer |
| `docs/learning/P01-project-foundation.md` | Explain implementation and engineering concepts | Documentation | Developer learning/review |

An ignored local `.env` was populated during troubleshooting after the initial implementation. It is a local operational artifact, not a source/configuration default. Its password is intentionally absent from this document. `.venv`, caches and temporary Docker resources are generated artifacts, not authored project files.

### `pyproject.toml`

**Purpose:** Describe one installable project and its development tools.

**Responsibility:** Declare the distribution name, Python compatibility, runtime/development dependency ranges, `uv_build` backend, strict typing, lint/format policy and pytest discovery/markers.

**Must NOT do:** Store credentials or duplicate business constants.

**Main components:** `[project]`, `[build-system]`, `[dependency-groups]` and the tool tables.

**Dependencies:** Compatible Python and uv installations; selected packages from the configured public registry.

**Used by:** Local setup, dependency updates, container installation and quality commands.

### `uv.lock`

**Purpose:** Preserve an exact dependency resolution beneath the allowed ranges.

**Responsibility:** Record package versions, dependency relationships, platform markers and downloadable artifact hashes.

**Must NOT do:** Become a hand-maintained substitute for package metadata or hold private registry credentials.

**Main components:** uv-generated package records, including runtime and development packages.

**Dependencies:** `pyproject.toml` and resolver output.

**Used by:** `uv sync --locked`, `uv run --locked` and Docker installation. Update it intentionally through uv, not by editing package records manually.

### `src/marketing_ai/main.py`

**Purpose:** Supply the ASGI composition entrypoint.

**Responsibility:** Return a fresh `FastAPI` instance with the project title.

**Must NOT do:** Connect to PostgreSQL/Redis, decrypt credentials, implement advertising rules or run AI work at import time.

**Main components:** `create_app() -> FastAPI`.

**Dependencies:** FastAPI only.

**Used by:** Uvicorn's factory mode and the `app` test fixture.

### `Dockerfile` and `.dockerignore`

**Purpose:** Turn the locked Python package into a runnable image while limiting its inputs.

**Responsibility:** Use pinned Python/uv bases, install the project non-editably without development dependencies, copy the environment into a clean runtime stage, switch to `app:app`, and execute Uvicorn.

**Must NOT do:** Copy `.env`, run migrations, connect to services during image construction or bake local credentials into layers.

**Main components:** uv, builder and runtime stages; explicit `COPY` operations; `uv sync --locked --no-dev --no-editable`; context allowlist; `USER` and exec-form `CMD`.

**Dependencies:** The build inputs, Docker, cached or reachable base images and Python artifacts.

**Used by:** Direct builds, optional Compose app and real container tests.

### `docker-compose.yml` and `.env.example`

**Purpose:** Provide local infrastructure without introducing application data models.

**Responsibility:** Configure loopback-bound services, PostgreSQL's local volume/password requirement, disposable Redis and the optional app profile.

**Must NOT do:** Define a production deployment, distribute secrets or imply that the app already uses these services.

**Main components:** `postgres`, `redis`, `app`, `postgres_data`, required password interpolation and infrastructure healthchecks.

**Dependencies:** Docker Compose and a local nonempty password when rendering the full stack.

**Used by:** Developer setup and isolated configuration tests.

### Test files

**Purpose:** Make foundation promises executable.

**Responsibility:** Test actual installation/import, app construction and transport behavior; exercise real Git/uv/Compose parsers; build and inspect actual containers.

**Must NOT do:** Mock the exact packaging/security claim being tested, touch the developer's database volume or pretend P01 implements business permissions.

**Main components:** Fixtures and tests listed in sections 9 and 14.

**Dependencies:** Installed project/dev environment; Git and Compose CLI for configuration tests; Docker daemon for the separately selected container suite.

**Used by:** Developers and P01 validation. All test secrets are synthetic canaries, not copied from local `.env`.

## 4. Files Modified

| File | What Changed | Why |
|---|---|---|
| `tests/test_p00_documentation.py` | Formatting/import whitespace only during initial P01 setup | Meet the newly configured Ruff rules; AST comparison verified unchanged behavior |
| `pyproject.toml` | Added named `container` marker and default selection excluding that marker | Keep quick checks daemon-free while providing an explicit mandatory container verification command |
| `tests/unit/test_imports.py` | Added no-network/no-settings import checks, exact route inventory and absent-business-route checks | Prove the foundation does not accidentally acquire service dependencies or expose business behavior |
| `README.md` | Added both suite commands, updated evidence and made `.env` copying conditional on absence | Make requirements reproducible and avoid overwriting an existing local password |

The implementation evolved from the synchronous test client to the `httpx2` ASGI transport with explicit lifespan. This follows the installed upstream API and avoids a deprecated AnyIO alias without suppressing warnings. No P00 architecture or business values changed. No domain, authentication, Meta, AI or business database code was added.

## 5. Architecture Explanation

The agreed future dependency direction remains:

```text
Presentation → Application → Domain ← Infrastructure
```

P01 instantiates only the entrypoint and development/deployment machinery. It does not create empty use cases or pretend that repositories/gateways already exist. Dependency inversion is an agreed design rule from P00, not an implemented repository mechanism in P01.

Actual components are:

```text
uv / installed Python environment
              │
              ▼
Uvicorn --factory ──► marketing_ai.main.create_app()
                                │
                                ▼
                         FastAPI instance
                                │
                  Default docs/OpenAPI routes

pytest ──► app fixture ──► explicit lifespan
                                │
                     HTTPX2 ASGITransport

Compose ──► PostgreSQL + Redis (separate local services)
                  No application connection yet
```

`create_app()` is a composition location: later implementations can wire dependencies there while keeping business behavior elsewhere. Each call returns independent state, allowing tests to avoid leaking one application's overrides into another.

## 6. Request / Data Flow

For a real documentation request:

1. Uvicorn imports `marketing_ai.main` from the installed environment.
2. `--factory` calls `create_app()` and receives an ASGI application.
3. Uvicorn manages startup/lifespan and receives an HTTP request.
4. FastAPI's framework routes handle `/openapi.json`, `/docs` or `/redoc`.
5. The OpenAPI schema contains no business paths.
6. An unknown path returns FastAPI/Starlette's default 404 response.

There is no principal resolution, application use case, domain rule or database query in that flow yet.

In in-process tests, HTTPX2 sends an ASGI scope directly to the app instead of opening a TCP socket. The `client` fixture enters the app's lifespan explicitly because ASGI transport alone does not guarantee startup/shutdown execution. The actual Docker test separately verifies real Uvicorn/socket behavior inside an isolated container.

## 7. Theory You Need to Understand

### Src-layout packaging and import resolution

**Definition:** Application code lives under `src/`, separate from the repository root, and is installed as a package.

**Why it exists:** Python's current-directory import behavior can hide broken packaging: code may import locally even when it would be missing from a distribution.

**How we use it here:** `uv_build` installs `src/marketing_ai`; a subprocess imports it from a temporary directory using `python -I`, which ignores PYTHONPATH and user-site shortcuts.

**What could go wrong without it:** Tests succeed only from the checkout, while the installed/container application fails with `ModuleNotFoundError`.

### Application factories and isolation

**Definition:** A factory constructs and returns a new application instance rather than sharing a module-level mutable instance everywhere.

**Why it exists:** Construction, configuration and test state need controlled ownership.

**How we use it here:** `create_app()` creates fresh FastAPI state; the fixture calls it for each test.

**What could go wrong without it:** State, dependency overrides or routes added by one test can contaminate another.

### ASGI and lifespan

**Definition:** ASGI is the asynchronous server/application protocol. Lifespan messages describe startup and shutdown separately from request handling.

**Why it exists:** The server and application can evolve independently while agreeing how requests and resource lifecycle are managed.

**How we use it here:** Uvicorn is the server. In-process tests use ASGI transport plus explicit lifespan; real image tests execute Uvicorn's default command.

**What could go wrong without it:** A request test might pass while never exercising startup, or it could leave resources unclosed after a later phase introduces them.

### Dependency constraints versus locks

**Definition:** A range defines allowed versions; a lock records the exact selected versions and artifacts for a resolved environment.

**Why it exists:** Compatibility intent and installation repeatability solve different problems.

**How we use it here:** Bounds live in `pyproject.toml`; `uv.lock` fixes resolution; `--locked` rejects inconsistent metadata rather than silently updating it.

**What could go wrong without it:** The same source can behave differently after dependency releases. A lock also is not a permanent security guarantee: upgrades still require review and verification.

### Linting, formatting, typing and behavior tests

**Definition:** Linting finds selected code problems; formatting standardizes layout; static typing checks declared type relationships; tests execute selected behavior.

**Why it exists:** These tools detect different defect classes and cannot replace one another.

**How we use it here:** Ruff handles lint/format, mypy runs strictly, and pytest verifies installation, routes, configuration and containers.

**What could go wrong without it:** Correct formatting could be mistaken for functional correctness, or passing runtime examples could hide inconsistent interfaces.

### Container layers and least privilege

**Definition:** A container image is assembled from filesystem layers and runtime metadata. Least privilege grants a process only the access it needs.

**Why it exists:** Deployment needs portable artifacts without unnecessarily giving the app root access or copying local secrets.

**How we use it here:** A builder prepares the environment; runtime receives only that environment, runs as a non-root user and keeps code root-owned. Compose/container tests add a read-only filesystem, dropped capabilities and no privilege escalation.

**What could go wrong without it:** A process can modify its code, access unintended build artifacts or gain broader permissions than its work requires. Deleting a secret in a later layer would not reliably remove it from earlier layers; excluding it before build is better.

### Compose interpolation versus application settings

**Definition:** Compose substitutes environment values into service configuration before starting containers. Application settings are interpreted by the application itself.

**Why it exists:** Infrastructure startup and app configuration have separate lifecycles.

**How we use it here:** Compose requires `POSTGRES_PASSWORD`; P01's app has no settings loader. A blank password stops configuration parsing before a database starts.

**What could go wrong without it:** A developer might try changing Python code to fix a Compose interpolation failure, or assume a running container means the app has connected to it.

### Test separation and realistic evidence

**Definition:** Unit/configuration tests check small behavior cheaply; integration tests combine actual components and their operational constraints.

**Why it exists:** Mocking everything can hide packaging, permissions, filesystem and entrypoint failures.

**How we use it here:** Default tests are fast and daemon-free; explicit container tests build/run Docker and inspect actual results. Both are required for the phase gate.

**What could go wrong without it:** A static assertion that a Dockerfile contains `USER` could pass even if the built process actually runs as root.

## 8. Practical Implementation Explanation

The entire app factory has a narrow contract:

```python
def create_app() -> FastAPI:
    return FastAPI(title="Maroc Affiliate AI Marketing Assistant")
```

It has no arguments and produces an independent application. Its dependency is FastAPI. Import errors indicate an installation problem; external-service failures cannot occur because no external calls exist here. Keeping the function small preserves a clear future wiring point.

The build command installs only runtime requirements:

```text
uv sync --locked --no-dev --no-editable --no-cache
```

Input is package metadata, the lockfile and source. Output is an installed environment copied into the runtime stage. `--no-editable` prevents an installed package from depending on a checkout path left behind in the builder. Missing registry artifacts or a stale lock fails the build rather than producing a guessed environment.

Compose contains a fail-fast input expression:

```yaml
POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?Set POSTGRES_PASSWORD in your local .env}
```

Input is local environment/.env; output is the database container environment. The example leaves this value blank so a developer must configure it locally. Tests render copied configuration with synthetic values and never display the real password.

The container marker separates resource requirements. Ordinary pytest deselects Docker tests; `-m container` selects them explicitly. This is not an optional verification shortcut: the validation report records both commands and their results.

## 9. Important Classes, Functions, Interfaces, and Schemas

| Name | Type | File | Responsibility |
|---|---|---|---|
| `create_app` | Function | `src/marketing_ai/main.py` | Return independent FastAPI app |
| `app` | Pytest fixture | `tests/conftest.py` | Construct test application |
| `anyio_backend` | Pytest fixture | `tests/conftest.py` | Select asyncio for asynchronous tests |
| `client` | Async fixture | `tests/conftest.py` | Manage lifespan and HTTPX2 ASGI client |
| `compose_config` | Test helper | `tests/unit/test_foundation.py` | Invoke real Compose parser using isolated inputs |
| `compose_project` | Test fixture | `tests/unit/test_foundation.py` | Copy Compose config and blank temporary .env |
| `docker` | Test helper | `tests/integration/test_container.py` | Run checked Docker commands with deadlines |
| `build_context` | Test fixture | `tests/integration/test_container.py` | Copy build inputs and synthetic canaries |
| `image` | Test fixture | `tests/integration/test_container.py` | Build a uniquely tagged runtime image and clean its tag |

There are no project-defined domain classes, protocols, request schemas, database models or repository interfaces in P01. Framework objects are used directly at the entrypoint/test boundary.

## 10. Database Changes

No database changes were introduced in this phase.

Compose provisions local infrastructure: PostgreSQL initializes its configured local database/role and system catalogs on a fresh volume. That is different from an application schema migration. P01 adds no business tables, columns, relationships, constraints, indexes, ORM models or transaction logic. Redis persistence is disabled because its local role is disposable coordination infrastructure.

The user's local PostgreSQL and Redis were started during setup troubleshooting and database authentication was checked. The P01 tests do not modify those services or their volume.

## 11. API Changes

No business API was added. The factory introduces the following default framework surface:

| Method/path | Purpose | Authentication/authorization | Request/response | Errors/use case |
|---|---|---|---|---|
| `GET /openapi.json` | Generated schema | Public in this foundation | No payload; JSON schema with empty `paths` | Framework handling; no use case |
| `GET /docs` | Swagger UI page | Public | HTML documentation shell | No business operation |
| `GET /docs/oauth2-redirect` | Default Swagger redirect helper | Public | HTML helper page | Its presence does not implement OAuth or grant identity |
| `GET /redoc` | ReDoc page | Public | HTML documentation shell | No business operation |

The tested existing endpoints return 200. Unknown paths, including `/`, `/health`, `/admin` and the tested campaign URLs, return default 404 JSON. No custom error envelope, principal resolution, seller lookup or request-ID middleware exists in P01. Documentation HTML may reference browser-loaded upstream assets; tests prove the HTML response, not offline rendering of those assets.

## 12. Security Considerations

- `.gitignore` protects ordinary additions of local environment files; a developer can still override Git ignore rules, so it is not a secret vault.
- `.env.example` contains no password. The actual local password was generated privately, stored in ignored `.env` with restricted filesystem permissions and never copied into this document.
- `.dockerignore` excludes secrets from the build context. A real probe build tests exclusion before application `COPY` instructions.
- Multi-stage installation excludes test/lint/type-check dependencies from runtime.
- The runtime process is non-root and cannot write its root-owned installed package. Read-only filesystem, dropped capabilities and no-new-privileges are exercised by container tests.
- Local service ports bind to loopback. The app service receives no database credentials in P01.
- No seller-data or financial endpoint exists. Tests verify absence; they do not claim RBAC, tenant isolation or approval enforcement has already been implemented.

There is no initialized Git index in this workspace. Review covers intended source/distribution inputs and tested ignore behavior; it is not represented as an audit of nonexistent tracked-file history.

## 13. Error Handling

| Failure | Expected Behavior | Why |
|---|---|---|
| Package not installed | Import fails | Test must expose packaging mistakes rather than add PYTHONPATH shortcuts |
| Missing/blank Compose password | Compose configuration fails with required-variable message | Database should not start with an accidental blank credential |
| Stale dependency metadata | Locked/offline verification fails and preserves lockfile | Changes need explicit resolution/review |
| Unavailable dependency registry/base image | Install/build fails | No unverified package substitution is made |
| Docker daemon inaccessible | Container suite fails clearly | Missing integration evidence must not become a skip/pass |
| Unknown/malformed request to absent business path | Default 404; no input echo | There is no business handler to process it |
| Unavailable PostgreSQL/Redis | App still starts in P01 | It has no connection code yet |

There is no multi-layer application error translation in this phase. Python/build tools report their own errors, and HTTP unknown routes use the framework's default response. Later error infrastructure must not be described as present now.

## 14. Testing Strategy

### Unit Tests

`test_package_imports_outside_repository` proves installation works without current-directory/PYTHONPATH help. `test_factory_creates_independent_apps` checks state isolation. `test_import_and_factory_do_not_connect_or_require_settings` uses missing/invalid dependency settings and connection functions that fail if called; the mocked boundary is network connection, not a business rule.

Git ignore tests invoke real Git in a temporary repository. The lock test first verifies valid metadata using real uv, changes the temporary project version, then proves failure without lock rewriting. With an empty offline cache, uv can report unavailable resolver metadata; the claim is fail-closed drift handling, not one specific diagnostic string.

### Integration Tests

The real Docker suite builds the actual runtime target from copied inputs. It checks the non-root process, root-owned package, runtime-only environment, Uvicorn's default command and local HTTP responses without external networking. A separate context-probe build checks that root/nested environment files, a key canary and test fixtures are excluded while application source remains available.

Unique image tags and container IDs avoid collisions. Cleanup removes only test-owned resources. No live database volume is used.

### API Tests

In-process tests verify an empty OpenAPI schema, documentation responses, the exact framework route inventory, and 404 responses for absent business/admin paths. Synthetic authorization text and malformed bodies must not appear in those responses. This proves minimal exposure, not real authorization behavior.

### Security Tests

Git ignore behavior, blank example password, missing/empty Compose password, loopback bindings, absent app credential injection, image user/ownership, development-package exclusion and context canaries are exercised. Tests use synthetic values rather than actual developer credentials.

### Failure Tests

Configuration failures and import-time connection attempts are applicable. Provider timeouts, rate limits, expired OAuth tokens and partial financial mutations are not executable in P01 because no provider/mutation code exists. The validation report records these scope limits explicitly.

### Boundary Tests

Missing versus empty password and valid versus drifted lock metadata are applicable boundaries. Daily budget, instruction length and business pagination enforcement remain unimplemented; inherited P00 tests check the documentation constants, not runtime policies.

### Concurrency / Idempotency Tests

Independent app instances are tested for state leakage. No persistent mutation or idempotency mechanism exists, so financial concurrency/transaction tests do not apply. The container suite's unique resources prevent test collisions but do not constitute a business idempotency implementation.

## 15. Commands Used

```bash
uv sync --locked
uv run --locked python -c 'import marketing_ai'
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked mypy src tests
uv run --locked pytest -q
uv run --locked pytest -q -m container
uv run --locked uvicorn marketing_ai.main:create_app --factory --host 127.0.0.1 --port 8000 --reload
```

Sync creates the installed environment; import verifies package visibility; the next commands check quality; the two test selections jointly cover the phase; Uvicorn serves the factory.

```bash
test -e .env || cp .env.example .env
docker compose config --quiet
docker compose up -d --wait postgres redis
docker compose ps
docker build -t marketing-ai:p01 .
docker run --rm --entrypoint id marketing-ai:p01
docker run --rm -p 127.0.0.1:8000:8000 marketing-ai:p01
```

Set a local password privately before rendering/starting Compose. The copy guard preserves an existing `.env`. Do not print the full rendered Compose configuration in a shared log because it can contain the resolved password. `config --quiet` validates without displaying it.

No Alembic command applies: migrations do not exist. Sandbox verification used a temporary uv cache through `UV_CACHE_DIR`; that environment-specific path is not required for a normal developer installation.

## 16. How to Test It Manually

1. Synchronize the environment and run the import command from section 15.
2. Run lint, formatting, typing and both test selections. The container selection needs Docker daemon access.
3. Start Uvicorn using the documented factory command.
4. Visit `/openapi.json`: expect 200 and no business paths. Visit `/docs`: expect HTML.
5. Request `/health` or a campaign URL: expect 404 at the P01 checkpoint.
6. Build the image and run `id` through the documented entrypoint override: the UID must not be root.
7. Run the image and repeat the HTTP checks.
8. In an isolated copied Compose project, leave the password blank and run `config --quiet`: expect failure before startup. Do not erase the real password to perform a negative test.
9. Inspect `docker compose ps` for local services if you chose to start them. Their healthy status does not prove an application database connection, because P01 has none.

## 17. Design Decisions

### Src layout and uv lock

**Decision:** Use an installed src-layout package with uv-compatible metadata and a committed lock.

**Why:** Import behavior and dependency resolution should match deployment.

**Alternatives:** A flat script directory or unpinned pip requirements.

**Why alternatives were not selected:** They make current-directory imports and environment drift easier to miss; no existing approved team toolchain had to be preserved.

### Factory without business routes

**Decision:** Construct an independent minimal app.

**Why:** Establish a composition point and executable baseline before adding capabilities.

**Alternatives:** A global app with sample business routes or early service initialization.

**Why alternatives were not selected:** Samples could look like real authorized behavior and early connections would couple import/startup to unimplemented dependencies.

### HTTPX2 ASGI tests plus real Uvicorn tests

**Decision:** Use explicit async lifespan for fast tests and Docker for actual server verification.

**Why:** Each proves something the other cannot.

**Alternatives:** Only mocked routes, only synchronous TestClient, or only slow container tests.

**Why alternatives were not selected:** Mocked-only checks miss installation/runtime issues; the installed synchronous client emitted an upstream deprecation; container-only feedback is unnecessarily slow. Warnings were not suppressed.

### Multi-stage non-root image

**Decision:** Copy only a non-editable runtime environment into a pinned base and switch user.

**Why:** Minimize runtime contents and privileges.

**Alternatives:** Copy the entire repository/host virtual environment or run as root.

**Why alternatives were not selected:** Those paths can distribute local secrets, incompatible binaries and unnecessary tooling or permissions.

### Separate container test marker

**Decision:** Run daemon-free defaults and explicitly select real container tests for validation.

**Why:** Make resource requirements visible without silently skipping required evidence.

**Alternatives:** Always build containers during every quick test or skip when Docker is unavailable.

**Why alternatives were not selected:** Always-building slows normal feedback; skipping could disguise a failed acceptance gate.

## 18. What I Should Learn From This Phase

After this phase I should understand:

- [ ] Why importing from outside the repository tests packaging better than PYTHONPATH injection.
- [ ] How a factory isolates app state.
- [ ] Why ASGI request transport and lifespan are separate.
- [ ] Why constraints and a lockfile are both useful.
- [ ] What Ruff, mypy and pytest each prove.
- [ ] Why a secret should be excluded before Docker receives the context.
- [ ] How non-root, read-only filesystems and dropped capabilities differ.
- [ ] Why Compose interpolation can fail before a service starts.
- [ ] Why passing local infrastructure healthchecks is not proof of application persistence.
- [ ] Why real container tests remain necessary alongside in-process tests.

## 19. Interview Questions From This Phase

**Q1 — Beginner: Why is the import name `marketing_ai` while the project name is `marketing-ai`?**

Python identifiers use underscores; distribution names and module import names are separate concepts.

**Q2 — Beginner: What does Uvicorn's `--factory` mean here?**

It calls `create_app()` to obtain the ASGI application rather than treating the function itself as the app.

**Q3 — Intermediate: Why test with `python -I` outside the checkout?**

It removes common import shortcuts and proves the installed environment exposes the package.

**Q4 — Intermediate: Why explicitly enter lifespan in the async client fixture?**

An ASGI transport can send requests without driving startup/shutdown; entering lifespan makes lifecycle execution deliberate.

**Q5 — Architecture: Where are the application and domain layers?**

They are designed in P00 but not implemented in P01. The entrypoint must remain small so later wiring preserves those boundaries.

**Q6 — Debugging: Why does Compose reject a blank password although the Python app starts?**

Compose validates its own required service input; P01's app does not load or use database settings.

**Q7 — Security: Does `.gitignore` remove a secret already committed to history?**

No. Ignore rules affect ordinary additions of untracked files; they do not repair tracked files or history.

**Q8 — Advanced: Why use `--no-editable` in the image build?**

The runtime receives only the installed environment; it cannot rely on source paths that existed only in the builder.

**Q9 — Tradeoff: Does a lockfile mean dependencies never need updating?**

No. It makes installations predictable; maintenance still requires intentional security/compatibility updates and rerunning checks.

**Q10 — Testing: What does an absent `/admin` endpoint prove?**

It proves the foundation exposes no admin handler. It does not prove an RBAC implementation that does not yet exist.

## 20. Common Mistakes

| Mistake | Why it is problematic | Correct approach |
|---|---|---|
| Add `src` to PYTHONPATH to fix tests | Masks a broken package installation | Install with uv and test outside the checkout |
| Copy `.env.example` over an existing `.env` | Erases the configured password and can break an existing database setup | Copy only when the local file is absent |
| Copy the whole repository into Docker | Sends unnecessary files and possibly secrets to the builder | Use explicit inputs and an allowlist |
| Assume `USER` text alone proves non-root execution | Later build/runtime changes may invalidate the assumption | Inspect the actual process in the built image |
| Ignore all warnings to pass tests | Conceals compatibility problems | Use supported interfaces and keep warnings actionable |
| Treat 404 checks as tenant authorization tests | There is no seller endpoint to authorize yet | State applicability limits and test real permissions when implemented |
| Run only the default pytest selection for the phase gate | Leaves container acceptance unverified | Run the explicit container suite too |

## 21. Debugging Guide

**Problem:** `ModuleNotFoundError: marketing_ai`.

**Possible cause:** Wrong interpreter or project not installed.

**How to diagnose:** Run the documented import using `uv run --locked`.

**How to fix:** Synchronize the locked environment; do not add a source-path workaround.

**Problem:** Required `POSTGRES_PASSWORD` interpolation fails.

**Possible cause:** Missing/empty local value, wrong working directory or an empty exported override.

**How to diagnose:** Confirm `.env` exists and has a nonempty assignment without printing its value; use `docker compose config --quiet`.

**How to fix:** Set the password privately in the local file and remove any unintended empty shell override. Do not reset or delete the PostgreSQL volume as a first response.

**Problem:** Password changed in `.env` but an existing database rejects it.

**Possible cause:** PostgreSQL initialized its credentials when the persistent volume was created; changing an environment file is not a database password migration.

**How to diagnose:** Check authentication through the intended connection without logging credentials.

**How to fix:** Reconcile the local configuration with the existing database's credentials through an authorized password change; preserve data.

**Problem:** Container tests cannot reach the daemon.

**Possible cause:** Docker is stopped, permissions are missing or a sandbox blocks its socket.

**How to diagnose:** Use `docker version` and inspect its server result.

**How to fix:** Restore authorized Docker access and rerun the container selection; do not report a skipped test as passed.

**Problem:** Locked commands reject metadata changes.

**Possible cause:** `pyproject.toml` and `uv.lock` disagree or an offline resolver lacks required metadata.

**How to diagnose:** Compare the intentional metadata change and run the lock check.

**How to fix:** Resolve through `uv lock` with approved registry access, review the lock diff, then rerun all checks.

**Problem:** Docker prints a legacy-builder notice.

**Possible cause:** Docker Buildx is not installed in the environment.

**How to diagnose:** Distinguish the notice from the final build exit status.

**How to fix:** Install the supported Buildx plugin through the normal environment setup; a successful legacy build is still recorded honestly as such.

## 22. Connection to Previous Phases

P00 provides the architecture baseline, safety invariants, canonical vocabulary, approved business constants and dependency roadmap. P01 translates only the foundation portion into executable tooling. Its default test run retains all P00 documentation checks. Business values remain in the central document and have not been duplicated into the package.

## 23. Preparation for the Next Phase

P02 receives an installed package, a tested `create_app()` composition point, fixture-based app construction, a configured quality toolchain, locked dependencies, container packaging and documented commands. It can introduce settings, logging, errors and health behavior in the intended locations. P01 guarantees only its verified foundation contracts; it does not guarantee future settings validation, request correlation or database readiness.

## 24. Final Phase Summary

### In one sentence

P01 provides a reproducible, testable Python/FastAPI foundation that builds and runs with constrained inputs and privileges.

### Before this phase

The project had architecture and business-policy documents plus document checks, but no installable app or container.

### After this phase

The package imports independently, serves minimal documentation, passes quality/configuration tests and runs in a verified non-root container; local infrastructure can be started separately.

### Most important engineering lesson

A foundation is trustworthy when its installation, boundaries and operational claims are demonstrated by the correct kind of test, with unimplemented behavior clearly identified.
