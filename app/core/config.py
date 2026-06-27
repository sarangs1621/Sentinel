from functools import lru_cache
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    ENVIRONMENT: str = "development"
    PROJECT_NAME: str = "Sentinel"
    API_V1_PREFIX: str = "/api/v1"

    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    LOG_FORMAT: Literal["text", "json"] = "text"

    # Error tracking (optional). Leave unset to disable Sentry entirely.
    SENTRY_DSN: str | None = None
    SENTRY_TRACES_SAMPLE_RATE: float = 0.0

    BACKEND_CORS_ORIGINS: list[str] = []

    SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    DATABASE_URL: str
    TEST_DATABASE_URL: str | None = None

    # SQLAlchemy async engine connection pool tuning.
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE_SECONDS: int = 1800
    DB_POOL_PRE_PING: bool = True

    POSTGRES_USER: str = "sentinel"
    POSTGRES_PASSWORD: str = "sentinel"
    POSTGRES_DB: str = "sentinel"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432

    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_TASK_ALWAYS_EAGER: bool = False
    CHECK_DISPATCH_INTERVAL_SECONDS: float = 10.0
    METRICS_AGGREGATION_INTERVAL_SECONDS: float = 3600.0

    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW_SECONDS: int = 60

    # Stricter rate limits for /auth/login and /auth/register, on top of the general limiter.
    AUTH_RATE_LIMIT_REQUESTS: int = 5
    AUTH_RATE_LIMIT_WINDOW_SECONDS: int = 60

    # Account lockout after repeated failed login attempts for the same email.
    MAX_LOGIN_FAILURES: int = 5
    LOGIN_LOCKOUT_WINDOW_SECONDS: int = 900

    MAX_REQUEST_BODY_BYTES: int = 1_048_576

    HSTS_MAX_AGE_SECONDS: int = 63072000

    RESEND_API_KEY: str | None = None
    EMAIL_FROM_ADDRESS: str = "onboarding@resend.dev"

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, value: object) -> object:
        if isinstance(value, str) and not value.startswith("["):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def normalize_database_url(cls, value: object) -> object:
        """Convert Render-style postgres:// URLs to SQLAlchemy asyncpg format and handle sslmode query param."""
        if isinstance(value, str):
            if value.startswith("postgres://"):
                value = value.replace("postgres://", "postgresql+asyncpg://", 1)
            elif value.startswith("postgresql://"):
                value = value.replace("postgresql://", "postgresql+asyncpg://", 1)
            
            # Convert sslmode=require to ssl=require for asyncpg compatibility
            if "sslmode=" in value:
                value = value.replace("sslmode=", "ssl=")
        return value

    @model_validator(mode="after")
    def _validate_secret_key(self) -> "Settings":
        if self.ENVIRONMENT != "testing" and len(self.SECRET_KEY) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters outside the testing environment.")
        return self

    @model_validator(mode="after")
    def _validate_cors_origins(self) -> "Settings":
        if "*" in self.BACKEND_CORS_ORIGINS:
            raise ValueError("BACKEND_CORS_ORIGINS must not contain '*'; list explicit origins instead.")
        return self

    @property
    def is_testing(self) -> bool:
        return self.ENVIRONMENT == "testing"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
