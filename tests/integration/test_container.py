"""Real Docker checks: explicit -m container, unique resources, no user services.

Builds repository inputs in a temporary context with synthetic secret canaries.
No actual .env is read/copied and no host port or database volume is used.
"""

import json
import re
import shutil
import subprocess
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.container


def docker(*arguments: str, timeout: int = 120) -> str:
    result = subprocess.run(["docker", *arguments], capture_output=True, text=True, timeout=timeout)
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout.strip()


@pytest.fixture(scope="module")
def build_context(tmp_path_factory: pytest.TempPathFactory) -> Path:
    context = tmp_path_factory.mktemp("p01-container")
    for filename in (
        "pyproject.toml",
        "uv.lock",
        "README.md",
        "Dockerfile",
        ".dockerignore",
        "alembic.ini",
    ):
        shutil.copyfile(ROOT / filename, context / filename)
    shutil.copytree(ROOT / "src", context / "src", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(
        ROOT / "migrations", context / "migrations", ignore=shutil.ignore_patterns("__pycache__")
    )
    for filename in (
        ".env",
        ".env.production",
        "src/marketing_ai/.env",
        "src/marketing_ai/test.key",
    ):
        (context / filename).write_text("p01-synthetic-secret-canary\n")
    (context / "tests").mkdir()
    (context / "tests" / "private-fixture.txt").write_text("not-for-container\n")
    return context


@pytest.fixture(scope="module")
def image(build_context: Path) -> Iterator[str]:
    tag = "marketing-ai-p01-test:" + uuid.uuid4().hex
    docker("build", "--target", "runtime", "-t", tag, str(build_context), timeout=300)
    try:
        yield tag
    finally:
        docker("image", "rm", tag)


def test_runtime_is_nonroot_and_excludes_development_files(image: str) -> None:
    code = """
import importlib.util
import json
import os
from pathlib import Path
import marketing_ai
assert os.geteuid() != 0
assert not any(Path('/app').rglob('.env*'))
assert not any(Path('/app').rglob('test.key'))
for module in ('pytest', 'ruff', 'mypy', 'httpx2'):
    assert importlib.util.find_spec(module) is None, module
package = Path(marketing_ai.__file__)
assert package.stat().st_uid == 0
assert not os.access(package, os.W_OK)
assert not any(key.startswith('POSTGRES_') for key in os.environ)
print(json.dumps({'uid': os.geteuid(), 'package_import': True}))
"""
    output = docker(
        "run",
        "--rm",
        "--read-only",
        "--tmpfs",
        "/tmp",
        "--network",
        "none",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges:true",
        "--entrypoint",
        "python",
        image,
        "-c",
        code,
    )
    assert json.loads(output)["uid"] != 0


def test_default_command_serves_http_without_external_services(
    image: str,
    tmp_path: Path,
    database_test_values: dict[str, str],
    identity_test_values: dict[str, str],
) -> None:
    # Only non-secret example values are passed; the developer's .env is never read.
    runtime_environment = tmp_path / "runtime.env"
    runtime_environment.write_text(
        "\n".join(
            line
            for line in (ROOT / ".env.example").read_text().splitlines()
            if line
            and not line.startswith(
                ("#", "POSTGRES_", "DATABASE_", "COMPOSE_", "REDIS_URL=", "IDENTITY_")
            )
        )
        + "\n"
        + "\n".join(f"{key}={value}" for key, value in database_test_values.items())
        + "\n"
        + "\n".join(f"{key}={value}" for key, value in identity_test_values.items())
        + "\n"
    )
    container = docker(
        "run",
        "--rm",
        "-d",
        "--read-only",
        "--tmpfs",
        "/tmp",
        "--network",
        "none",
        "--env-file",
        str(runtime_environment),
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges:true",
        image,
    )
    try:
        code = """
import json
import time
from urllib.error import HTTPError, URLError
from urllib.request import urlopen
deadline = time.monotonic() + 20
while True:
    try:
        with urlopen('http://127.0.0.1:8000/openapi.json', timeout=2) as response:
            assert response.status == 200
            assert set(json.load(response)['paths']) == {'/health/live', '/health/ready', '/meta/connections', '/meta/connections/start', '/meta/connections/{connection_id}'}
        break
    except URLError:
        if time.monotonic() >= deadline:
            raise
        time.sleep(0.1)
with urlopen('http://127.0.0.1:8000/docs', timeout=2) as response:
    assert response.status == 200
with urlopen('http://127.0.0.1:8000/health/live', timeout=2) as response:
    assert response.status == 200
    assert response.headers['X-Request-ID']
try:
    urlopen('http://127.0.0.1:8000/health/ready', timeout=5)
except HTTPError as error:
    assert error.code == 503
    assert json.load(error)['error']['code'] == 'DEPENDENCY_UNAVAILABLE'
else:
    raise AssertionError('P03 readiness must fail without PostgreSQL')
try:
    urlopen('http://127.0.0.1:8000/health', timeout=2)
except HTTPError as error:
    assert error.code == 404
else:
    raise AssertionError('Unexpected bare /health alias')
print('HTTP startup and minimal routes: PASS')
"""
        assert "PASS" in docker("exec", container, "python", "-c", code, timeout=60)
    finally:
        docker("rm", "-f", container)


def test_dockerignore_excludes_secrets_from_build_context(build_context: Path) -> None:
    # A separate probe COPYs the context, proving exclusion before any app-layer COPY.
    source = (ROOT / "Dockerfile").read_text()
    base = re.findall(r"^FROM (\S+) AS runtime$", source, re.M)[0]
    probe = build_context / "ContextProbe.Dockerfile"
    probe.write_text(
        f"FROM {base}\nCOPY . /context\n"
        "RUN test ! -e /context/.env && test ! -e /context/.env.production "
        "&& test ! -e /context/src/marketing_ai/.env "
        "&& test ! -e /context/src/marketing_ai/test.key "
        "&& test ! -e /context/tests "
        "&& test -f /context/src/marketing_ai/main.py\n"
    )
    tag = "marketing-ai-p01-context-test:" + uuid.uuid4().hex
    try:
        docker("build", "-f", str(probe), "-t", tag, str(build_context), timeout=300)
    finally:
        # If the build failed before tagging, there is no owned image to remove.
        if docker("image", "ls", "-q", tag):
            docker("image", "rm", tag)
