# Marketing

## Maroc Affiliate AI Marketing Assistant

The architecture baseline and implementation guardrails for the marketing assistant are frozen in P00:

- [Architecture overview](docs/architecture/overview.md)
- [Domain glossary](docs/architecture/domain-glossary.md)
- [Non-functional requirements](docs/architecture/non-functional-requirements.md)
- [Architecture decision records](docs/adr/)

## Repository foundation

The project uses a Python 3.14 src layout, uv for dependency management, FastAPI for
the minimal ASGI entrypoint, Ruff for formatting/linting, mypy for type checking,
and pytest for tests. P01 intentionally provides no business routes, configuration
loading, database access, authentication, or external integrations.

### Local setup

Install Python 3.14 and uv, then create a local-only environment file and synchronize
the lockfile:

~~~bash
cp .env.example .env
uv sync --locked
uv run python -c 'import marketing_ai'
~~~

The placeholders in .env.example are safe local-development values. Replace the local
database password before sharing a development environment; never commit .env.

### Quality commands

Run these from the repository root:

~~~bash
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests
uv run pytest -q
~~~

### Run the application

The P01 app exposes only a bootstrap response and a non-sensitive health endpoint:

~~~bash
uv run uvicorn --factory marketing_ai.main:create_app --host 127.0.0.1 --port 8000 --reload
curl http://127.0.0.1:8000/health
~~~

### Local containers

Build and run the application image:

~~~bash
docker build --tag marketing-ai:p01 .
docker run --rm --publish 127.0.0.1:8000:8000 marketing-ai:p01
~~~

Start only local PostgreSQL and Redis:

~~~bash
docker compose up -d postgres redis
~~~

Start the optional application profile after those services are healthy:

~~~bash
docker compose --profile app up --build
~~~

Stop local infrastructure with:

~~~bash
docker compose down
~~~
