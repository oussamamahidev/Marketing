"""Typed centralized settings; no dependency connections or business operations.

The environment supplies the approved BUSINESS_CONSTANTS values. Required
values have no fallback; main loads them before serving. Tested in test_config.
"""

from decimal import Decimal
from typing import Annotated, Literal, Self
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, ValidationError, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic_settings.exceptions import SettingsError
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

PositiveInt = Annotated[int, Field(gt=0)]
NonnegativeInt = Annotated[int, Field(ge=0)]
Money = Annotated[Decimal, Field(ge=0, decimal_places=2, allow_inf_nan=False)]
PositiveMoney = Annotated[Decimal, Field(gt=0, decimal_places=2, allow_inf_nan=False)]
Percentage = Annotated[Decimal, Field(ge=0, le=100, allow_inf_nan=False)]
NonEmptyText = Annotated[str, Field(min_length=1)]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
        hide_input_in_errors=True,
        frozen=True,
    )

    ENVIRONMENT: Literal["local", "test", "staging", "production"]
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    DATABASE_URL: SecretStr = Field(repr=False, exclude=True)
    DATABASE_POOL_SIZE: PositiveInt
    DATABASE_MAX_OVERFLOW: NonnegativeInt
    DATABASE_POOL_TIMEOUT_SECONDS: PositiveInt
    DATABASE_CONNECT_TIMEOUT_SECONDS: PositiveInt
    DATABASE_READINESS_TIMEOUT_SECONDS: PositiveInt
    REDIS_URL: SecretStr | None = Field(default=None, repr=False, exclude=True)
    POSTGRES_PASSWORD: SecretStr | None = Field(default=None, repr=False, exclude=True)
    IDENTITY_JWT_ISSUER: NonEmptyText
    IDENTITY_JWT_AUDIENCE: NonEmptyText
    IDENTITY_JWT_HS256_SECRET: SecretStr = Field(repr=False, exclude=True)
    META_OAUTH_STATE_SIGNING_SECRET: SecretStr | None = Field(
        default=None, repr=False, exclude=True
    )
    META_OAUTH_STATE_TTL_SECONDS: PositiveInt | None = None
    CATALOG_SERVICE_BASE_URL: str | None = None
    INVENTORY_SERVICE_BASE_URL: str | None = None
    ORDERS_SERVICE_BASE_URL: str | None = None
    CONTENT_HUB_SERVICE_BASE_URL: str | None = None
    INTERNAL_SERVICE_IDENTITY: SecretStr | None = Field(default=None, repr=False, exclude=True)
    INTERNAL_READ_TIMEOUT_SECONDS: PositiveInt | None = None
    INTERNAL_READ_MAX_RETRIES: NonnegativeInt | None = None
    CONTENT_HUB_APPROVED_STORAGE_HOSTS: tuple[NonEmptyText, ...] = ()

    PLATFORM_CURRENCY: Literal["MAD"] = "MAD"
    MONEY_STORAGE: Literal["integer centimes"] = "integer centimes"
    META_ACCOUNT_CURRENCY_POLICY: Literal["reject mismatch"] = "reject mismatch"
    FX_CONVERSION: Literal["not supported in MVP"] = "not supported in MVP"

    MIN_DAILY_BUDGET_MAD: PositiveMoney
    MAX_DAILY_BUDGET_MAD: PositiveMoney
    MAX_DAILY_BUDGET_PER_SELLER_MAD: PositiveMoney
    MAX_BUDGET_INCREASE_PCT_PER_ACTION: Percentage
    MIN_HOURS_BETWEEN_BUDGET_CHANGES: PositiveInt
    BUDGET_CHANGE_REQUIRES_APPROVAL: bool
    MIN_STOCK_UNITS_TO_ADVERTISE: PositiveInt
    STOCK_FLOOR_TO_AUTO_PAUSE: PositiveInt
    MIN_GROSS_MARGIN_PCT: Percentage
    MAX_ACCEPTABLE_CANCELLATION_RATE_PCT: Percentage
    MAX_ACCEPTABLE_RETURN_RATE_PCT: Percentage
    MIN_ORDERS_FOR_RATE_CONFIDENCE: PositiveInt
    DELIVERY_COST_PER_ORDER_MAD: Money
    PROFITABILITY_ATTRIBUTION_WINDOW_DAYS: PositiveInt
    MIN_DAYS_BEFORE_PERFORMANCE_JUDGEMENT: PositiveInt
    MAX_GRAPH_STEPS: PositiveInt
    MAX_STRUCTURED_OUTPUT_RETRIES: NonnegativeInt
    LLM_REQUEST_TIMEOUT_SECONDS: PositiveInt
    MAX_INPUT_TOKENS_PER_RUN: PositiveInt
    MAX_OUTPUT_TOKENS_PER_RUN: PositiveInt
    MAX_AI_PROPOSALS_PER_SELLER_PER_DAY: PositiveInt
    MAX_LLM_COST_PER_SELLER_PER_DAY_MAD: Money
    MAX_SELLER_INSTRUCTION_CHARS: PositiveInt
    IDEMPOTENCY_KEY_TTL_HOURS: PositiveInt
    META_WRITE_TIMEOUT_SECONDS: PositiveInt
    MAX_RETRIES_META_WRITE: NonnegativeInt
    EXECUTING_STATE_STALE_AFTER_MINUTES: PositiveInt
    RECONCILIATION_SCAN_INTERVAL_MINUTES: PositiveInt
    APPROVAL_PAYLOAD_TTL_MINUTES: PositiveInt
    PERFORMANCE_SYNC_INTERVAL_MINUTES: PositiveInt
    PERFORMANCE_SNAPSHOT_RETENTION_DAYS: PositiveInt
    META_API_RATE_LIMIT_BUFFER_PCT: Percentage
    SYNC_BACKFILL_MAX_DAYS: PositiveInt
    DEFAULT_PAGE_SIZE: PositiveInt
    MAX_PAGE_SIZE: PositiveInt
    RATE_LIMIT_AUTHENTICATED_PER_MINUTE: PositiveInt
    RATE_LIMIT_AI_ENDPOINTS_PER_MINUTE: PositiveInt
    SSE_MAX_STREAM_DURATION_SECONDS: PositiveInt
    RTO_MINUTES: PositiveInt
    RPO_MINUTES: PositiveInt
    BACKUP_RETENTION_DAYS: PositiveInt
    RESTORE_TEST_FREQUENCY_DAYS: PositiveInt

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, value: SecretStr) -> SecretStr:
        try:
            url = make_url(value.get_secret_value())
            valid = (
                url.drivername == "postgresql+psycopg"
                and bool(url.host and url.database and url.username and url.password)
                and (url.port is None or 0 < url.port <= 65535)
            )
        except ArgumentError, ValueError:
            valid = False
        if not valid:
            raise ValueError("DATABASE_URL requires a PostgreSQL psycopg URL with credentials")
        return value

    @field_validator("IDENTITY_JWT_ISSUER", "IDENTITY_JWT_AUDIENCE")
    @classmethod
    def reject_blank_identity_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Identity issuer and audience cannot be blank")
        return value

    @field_validator(
        "CATALOG_SERVICE_BASE_URL",
        "INVENTORY_SERVICE_BASE_URL",
        "ORDERS_SERVICE_BASE_URL",
        "CONTENT_HUB_SERVICE_BASE_URL",
    )
    @classmethod
    def validate_internal_service_base_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        parsed = urlsplit(value)
        try:
            parsed.port
        except ValueError:
            raise ValueError(
                "Internal service URL must be an origin without credentials or query"
            ) from None
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
            or parsed.path not in {"", "/"}
        ):
            raise ValueError("Internal service URL must be an origin without credentials or query")
        return value.rstrip("/")

    @field_validator("CONTENT_HUB_APPROVED_STORAGE_HOSTS")
    @classmethod
    def validate_storage_hosts(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any("/" in host or ":" in host or host != host.lower() for host in value):
            raise ValueError("Approved storage hosts must be lowercase host names")
        return value

    @field_validator("IDENTITY_JWT_HS256_SECRET")
    @classmethod
    def reject_blank_identity_secret(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().strip():
            raise ValueError("Identity signing secret cannot be blank")
        return value

    @field_validator("META_OAUTH_STATE_SIGNING_SECRET")
    @classmethod
    def reject_blank_meta_state_secret(cls, value: SecretStr | None) -> SecretStr | None:
        if value is not None and not value.get_secret_value().strip():
            raise ValueError("Meta OAuth state signing secret cannot be blank")
        return value

    @field_validator(
        "MIN_DAILY_BUDGET_MAD",
        "MAX_DAILY_BUDGET_MAD",
        "MAX_DAILY_BUDGET_PER_SELLER_MAD",
        "DELIVERY_COST_PER_ORDER_MAD",
        "MAX_LLM_COST_PER_SELLER_PER_DAY_MAD",
        mode="before",
    )
    @classmethod
    def reject_float_money(cls, value: object) -> object:
        if isinstance(value, float):
            raise ValueError("Money configuration must use exact decimal text or integers")
        return value

    @model_validator(mode="after")
    def validate_policy_relationships(self) -> Self:
        if (self.META_OAUTH_STATE_SIGNING_SECRET is None) != (
            self.META_OAUTH_STATE_TTL_SECONDS is None
        ):
            raise ValueError("Meta OAuth state signing secret and TTL must be configured together")
        configured_service_urls = (
            self.CATALOG_SERVICE_BASE_URL,
            self.INVENTORY_SERVICE_BASE_URL,
            self.ORDERS_SERVICE_BASE_URL,
            self.CONTENT_HUB_SERVICE_BASE_URL,
        )
        shared_read_configuration = (
            self.INTERNAL_SERVICE_IDENTITY,
            self.INTERNAL_READ_TIMEOUT_SECONDS,
            self.INTERNAL_READ_MAX_RETRIES,
        )
        if any(configured_service_urls) and any(
            value is None for value in shared_read_configuration
        ):
            raise ValueError(
                "Internal service clients require identity, timeout, and retry configuration"
            )
        if self.CONTENT_HUB_SERVICE_BASE_URL and not self.CONTENT_HUB_APPROVED_STORAGE_HOSTS:
            raise ValueError("Content Hub requires approved storage hosts")

        if not self.BUDGET_CHANGE_REQUIRES_APPROVAL:
            raise ValueError("BUDGET_CHANGE_REQUIRES_APPROVAL must remain enabled")
        if not (
            self.MIN_DAILY_BUDGET_MAD
            <= self.MAX_DAILY_BUDGET_MAD
            <= self.MAX_DAILY_BUDGET_PER_SELLER_MAD
        ):
            raise ValueError("Daily budget minimum, maximum and seller ceiling are inconsistent")
        if self.STOCK_FLOOR_TO_AUTO_PAUSE >= self.MIN_STOCK_UNITS_TO_ADVERTISE:
            raise ValueError("Stock pause floor must be below advertising stock minimum")
        if self.DEFAULT_PAGE_SIZE > self.MAX_PAGE_SIZE:
            raise ValueError("Default page size exceeds maximum page size")
        if self.SYNC_BACKFILL_MAX_DAYS > self.PERFORMANCE_SNAPSHOT_RETENTION_DAYS:
            raise ValueError("Backfill window exceeds snapshot retention")
        if self.ENVIRONMENT in {"staging", "production"} and self.LOG_LEVEL == "DEBUG":
            raise ValueError("DEBUG logging is not allowed in staging or production")
        return self

    def money_centimes(self, name: str) -> int:
        """Convert a named MAD setting exactly; no float or DB Decimal values."""
        if name not in type(self).model_fields or not name.endswith("_MAD"):
            raise ValueError("Expected a named MAD configuration field")
        amount = getattr(self, name)
        if not isinstance(amount, Decimal):
            raise ValueError("Expected validated decimal money")
        # Integer arithmetic avoids rounding under a caller's Decimal context.
        numerator, denominator = amount.as_integer_ratio()
        return numerator * 100 // denominator  # Currency units, not a business threshold.


class ConfigurationError(RuntimeError):
    """Non-secret startup failure; raw settings inputs must not escape."""


def load_settings() -> Settings:
    try:
        return Settings()
    except ValidationError as exc:
        failures = []
        for error in exc.errors(include_input=False, include_context=False, include_url=False):
            field = str(error["loc"][0]) if error["loc"] else "configuration_relationships"
            failures.append(f"{field}: {error['type']}")
        raise ConfigurationError("Invalid configuration: " + "; ".join(failures)) from None
    except SettingsError:
        raise ConfigurationError("Invalid configuration: environment could not be parsed") from None
