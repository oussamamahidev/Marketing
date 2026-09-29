"""Disposable PostgreSQL only: generated credentials, private databases, cleanup.

Never read developer .env or connect to existing Compose services. Tests marked
database require Docker and fail explicitly when it is unavailable.
"""

import json
import secrets
import subprocess
import time
from collections.abc import Iterator
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from sqlalchemy.engine import URL


def docker(*arguments: str) -> str:
    result = subprocess.run(["docker", *arguments], capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


@pytest.fixture(scope="session")
def postgres_admin_url(tmp_path_factory: pytest.TempPathFactory) -> Iterator[URL]:
    password = secrets.token_urlsafe(24) + "%special"
    environment = tmp_path_factory.mktemp("p03-postgres") / "postgres.env"
    environment.write_text(
        f"POSTGRES_USER=p03_admin\nPOSTGRES_PASSWORD={password}\nPOSTGRES_DB=postgres\n"
    )
    environment.chmod(0o600)
    container = docker(
        "run",
        "--rm",
        "-d",
        "--env-file",
        str(environment),
        "--tmpfs",
        "/var/lib/postgresql/data:rw",
        "-p",
        "127.0.0.1::5432",
        "postgres:17-bookworm",
    )
    try:
        deadline = time.monotonic() + 30  # Test startup watchdog, not a business constant.
        while True:
            check = subprocess.run(
                [
                    "docker",
                    "exec",
                    container,
                    "pg_isready",
                    "-h",
                    "127.0.0.1",
                    "-U",
                    "p03_admin",
                    "-d",
                    "postgres",
                ],
                capture_output=True,
                timeout=5,
            )
            if check.returncode == 0:
                break
            assert time.monotonic() < deadline, "Disposable PostgreSQL did not become ready"
            time.sleep(0.1)
        ports = json.loads(
            docker("inspect", "--format", "{{json .NetworkSettings.Ports}}", container)
        )
        url = URL.create(
            "postgresql",
            username="p03_admin",
            password=password,
            host="127.0.0.1",
            port=int(ports["5432/tcp"][0]["HostPort"]),
            database="postgres",
        )
        with psycopg.connect(
            url.render_as_string(hide_password=False), autocommit=True
        ) as connection:
            connection.execute(
                sql.SQL(
                    "CREATE ROLE p03_test LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD {}"
                ).format(sql.Literal(password))
            )
        yield url
    finally:
        docker("rm", "-f", container)
        environment.unlink(missing_ok=True)


@pytest.fixture
def postgres_url(postgres_admin_url: URL) -> Iterator[URL]:
    name = "p03_" + uuid4().hex
    with psycopg.connect(
        postgres_admin_url.render_as_string(hide_password=False), autocommit=True
    ) as connection:
        connection.execute(
            sql.SQL("CREATE DATABASE {} OWNER p03_test").format(sql.Identifier(name))
        )
    try:
        yield postgres_admin_url.set(
            drivername="postgresql+psycopg", username="p03_test", database=name
        )
    finally:
        with psycopg.connect(
            postgres_admin_url.render_as_string(hide_password=False), autocommit=True
        ) as connection:
            connection.execute(
                sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name))
            )
