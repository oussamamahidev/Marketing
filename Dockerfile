# PURPOSE: Build a reproducible, least-privilege runtime image for the API process.
# RESPONSIBILITY: Installs locked runtime dependencies and runs the ASGI application as a non-root user; it does not contain secrets or development tooling.
# DEPENDENCIES: uv.lock, pyproject.toml, src/marketing_ai, pinned Python and uv images.
# USED BY: docker build and the optional Docker Compose app profile.
# TESTED BY: P01 Docker build, non-root, and startup smoke checks.

FROM ghcr.io/astral-sh/uv:0.11.26 AS uv

FROM python:3.14.4-slim-bookworm AS build

COPY --from=uv /uv /uvx /bin/

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0

COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

COPY src ./src
RUN uv sync --locked --no-dev --no-editable

FROM python:3.14.4-slim-bookworm AS runtime

RUN groupadd --system --gid 10001 marketingai \
    && useradd --system --uid 10001 --gid marketingai --create-home \
        --home-dir /app --shell /usr/sbin/nologin marketingai

WORKDIR /app

ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY --from=build --chown=marketingai:marketingai /app/.venv /app/.venv

USER marketingai

EXPOSE 8000

CMD ["uvicorn", "--factory", "marketing_ai.main:create_app", "--host", "0.0.0.0", "--port", "8000"]
