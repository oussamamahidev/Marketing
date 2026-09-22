"""Central configuration validation using approved values, never copied limits."""

import os
import re
import subprocess
import sys
from decimal import Decimal, localcontext
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from marketing_ai.core.config import ConfigurationError, Settings, load_settings

REQUIRED = [name for name, field in Settings.model_fields.items() if field.is_required()]


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    for field in Settings.model_fields:
        monkeypatch.delenv(field, raising=False)


def test_initial_values_match_binding_document(settings: Settings) -> None:
    root = Path(__file__).resolve().parents[3]
    rows = re.findall(
        r"^\| `([A-Z][A-Z0-9_]+)` \| `(\d+)` \|", (root / "BUSINESS_CONSTANTS.md").read_text(), re.M
    )
    for name, value in rows:
        assert getattr(settings, name) == Decimal(value), name


@pytest.mark.parametrize("missing", REQUIRED)
def test_every_required_setting_fails_if_missing(
    settings_values: dict[str, Any], missing: str
) -> None:
    values = settings_values.copy()
    values.pop(missing)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **values)


@pytest.mark.parametrize("invalid", ["", "<<SET>>", "not-a-number", "-1", "NaN", "Infinity"])
def test_invalid_budget_is_rejected(settings_values: dict[str, Any], invalid: str) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **(settings_values | {"MAX_DAILY_BUDGET_MAD": invalid}))


@pytest.mark.parametrize("offset", [-1, 0, 1])
def test_budget_ordering_boundary(settings_values: dict[str, Any], offset: int) -> None:
    ceiling = Decimal(settings_values["MAX_DAILY_BUDGET_MAD"])
    values = settings_values | {"MIN_DAILY_BUDGET_MAD": str(ceiling + offset)}
    if offset > 0:
        with pytest.raises(ValidationError):
            Settings(_env_file=None, **values)
    else:
        Settings(_env_file=None, **values)


@pytest.mark.parametrize("offset", [-1, 0, 1])
def test_page_boundary(settings_values: dict[str, Any], offset: int) -> None:
    values = settings_values | {
        "DEFAULT_PAGE_SIZE": str(int(settings_values["MAX_PAGE_SIZE"]) + offset)
    }
    if offset > 0:
        with pytest.raises(ValidationError):
            Settings(_env_file=None, **values)
    else:
        Settings(_env_file=None, **values)


def test_approval_cannot_be_disabled_or_settings_mutated(
    settings_values: dict[str, Any], settings: Settings
) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **(settings_values | {"BUDGET_CHANGE_REQUIRES_APPROVAL": "false"}))
    with pytest.raises(ValidationError):
        setattr(settings, "BUDGET_CHANGE_REQUIRES_APPROVAL", False)


@pytest.mark.parametrize("environment", ["staging", "production"])
def test_nonlocal_debug_is_rejected(settings_values: dict[str, Any], environment: str) -> None:
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None, **(settings_values | {"ENVIRONMENT": environment, "LOG_LEVEL": "DEBUG"})
        )


def test_secret_fields_never_appear_in_repr_or_serialization(
    settings_values: dict[str, Any],
) -> None:
    canary = "p02-test-secret-never-display"
    settings = Settings(
        _env_file=None,
        **(
            settings_values
            | {
                "DATABASE_URL": f"postgresql+psycopg://test:{canary}@localhost/test",
                "REDIS_URL": canary,
                "POSTGRES_PASSWORD": canary,
            }
        ),
    )
    assert canary not in repr(settings)
    assert canary not in settings.model_dump_json()
    assert not {"DATABASE_URL", "REDIS_URL", "POSTGRES_PASSWORD"} & settings.model_dump().keys()


def test_startup_failure_is_clear_without_input_values(monkeypatch: pytest.MonkeyPatch) -> None:
    canary = "p02-secret-as-invalid-environment"
    monkeypatch.setenv("ENVIRONMENT", canary)
    with pytest.raises(ConfigurationError) as caught:
        load_settings()
    assert "ENVIRONMENT" in str(caught.value)
    assert "MAX_DAILY_BUDGET_MAD" in str(caught.value)
    assert canary not in str(caught.value)


def test_environment_overrides_dotenv_without_exposing_secrets(
    settings_values: dict[str, Any], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / ".env").write_text("\n".join(f"{k}={v}" for k, v in settings_values.items()))
    monkeypatch.setenv("ENVIRONMENT", "production")
    assert load_settings().ENVIRONMENT == "production"


def test_money_conversion_is_exact_and_rejects_wrong_fields(
    settings_values: dict[str, Any],
) -> None:
    amount = Decimal(settings_values["DELIVERY_COST_PER_ORDER_MAD"]) + Decimal("0.01")
    settings = Settings(
        _env_file=None, **(settings_values | {"DELIVERY_COST_PER_ORDER_MAD": str(amount)})
    )
    assert settings.money_centimes("DELIVERY_COST_PER_ORDER_MAD") == int(amount * 100)
    with pytest.raises(ValueError):
        settings.money_centimes("MAX_PAGE_SIZE")
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            **(settings_values | {"DELIVERY_COST_PER_ORDER_MAD": str(amount + Decimal("0.001"))}),
        )
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None, **(settings_values | {"DELIVERY_COST_PER_ORDER_MAD": float(amount)})
        )


def test_money_conversion_is_independent_of_decimal_context(
    settings_values: dict[str, Any],
) -> None:
    amount = Decimal(settings_values["DELIVERY_COST_PER_ORDER_MAD"]) + Decimal("0.01")
    settings = Settings(
        _env_file=None, **(settings_values | {"DELIVERY_COST_PER_ORDER_MAD": amount})
    )
    expected = int(amount * 100)
    with localcontext() as context:
        # A computation elsewhere must not change exact configured centimes.
        context.prec = 2
        assert settings.money_centimes("DELIVERY_COST_PER_ORDER_MAD") == expected


@pytest.mark.parametrize(
    "field,ceiling,inclusive",
    [
        ("MAX_DAILY_BUDGET_MAD", "MAX_DAILY_BUDGET_PER_SELLER_MAD", True),
        ("STOCK_FLOOR_TO_AUTO_PAUSE", "MIN_STOCK_UNITS_TO_ADVERTISE", False),
        ("SYNC_BACKFILL_MAX_DAYS", "PERFORMANCE_SNAPSHOT_RETENTION_DAYS", True),
    ],
)
@pytest.mark.parametrize("offset", [-1, 0, 1])
def test_remaining_relationship_boundaries(
    settings_values: dict[str, Any], field: str, ceiling: str, inclusive: bool, offset: int
) -> None:
    values = settings_values | {field: str(int(settings_values[ceiling]) + offset)}
    if offset > 0 or (offset == 0 and not inclusive):
        with pytest.raises(ValidationError):
            Settings(_env_file=None, **values)
    else:
        assert getattr(Settings(_env_file=None, **values), field) == Decimal(values[field])


@pytest.mark.parametrize(
    "value,valid", [("-1", False), ("0", True), ("100", True), ("101", False), ("NaN", False)]
)
def test_percentage_domain(settings_values: dict[str, Any], value: str, valid: bool) -> None:
    # Percentage endpoints are mathematical bounds, not new business defaults.
    values = settings_values | {"MIN_GROSS_MARGIN_PCT": value}
    if valid:
        assert Settings(_env_file=None, **values).MIN_GROSS_MARGIN_PCT == Decimal(value)
    else:
        with pytest.raises(ValidationError):
            Settings(_env_file=None, **values)


@pytest.mark.parametrize(
    "field,value,valid",
    [
        ("MAX_GRAPH_STEPS", "0", False),
        ("MAX_GRAPH_STEPS", "1", True),
        ("MAX_GRAPH_STEPS", "1.5", False),
        ("MAX_RETRIES_META_WRITE", "-1", False),
        ("MAX_RETRIES_META_WRITE", "0", True),
        ("DELIVERY_COST_PER_ORDER_MAD", "0", True),
        ("DELIVERY_COST_PER_ORDER_MAD", "-0.01", False),
        ("PLATFORM_CURRENCY", "USD", False),
        ("BUDGET_CHANGE_REQUIRES_APPROVAL", "", False),
        ("ENVIRONMENT", "", False),
        ("LOG_LEVEL", "trace", False),
    ],
)
def test_scalar_configuration_boundaries(
    settings_values: dict[str, Any], field: str, value: str, valid: bool
) -> None:
    values = settings_values | {field: value}
    if valid:
        Settings(_env_file=None, **values)
    else:
        with pytest.raises(ValidationError):
            Settings(_env_file=None, **values)


@pytest.mark.parametrize("environment", ["local", "test", "staging", "production"])
def test_supported_environments_start(settings_values: dict[str, Any], environment: str) -> None:
    from marketing_ai.main import create_app

    settings = Settings(_env_file=None, **(settings_values | {"ENVIRONMENT": environment}))
    assert create_app(settings).state.settings is settings


@pytest.mark.parametrize("invalid", [None, "p02-startup-secret-canary"])
def test_real_factory_startup_rejects_bad_environment_without_leaking(
    settings_values: dict[str, Any], tmp_path: Path, invalid: str | None
) -> None:
    values = settings_values.copy()
    values.pop("ENVIRONMENT")
    if invalid is not None:
        values["ENVIRONMENT"] = invalid
    (tmp_path / ".env").write_text("\n".join(f"{key}={value}" for key, value in values.items()))
    result = subprocess.run(
        [sys.executable, "-I", "-c", "from marketing_ai.main import create_app; create_app()"],
        cwd=tmp_path,
        env={key: value for key, value in os.environ.items() if key not in Settings.model_fields},
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode != 0
    assert "ConfigurationError" in result.stderr and "ENVIRONMENT" in result.stderr
    assert "p02-startup-secret-canary" not in result.stdout + result.stderr
