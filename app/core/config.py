from functools import lru_cache

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

    BACKEND_CORS_ORIGINS: list[str] = []

    SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    DATABASE_URL: str
    TEST_DATABASE_URL: str | None = None

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

    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 587
    SMTP_USERNAME: str | None = None
    SMTP_PASSWORD: str | None = None
    SMTP_USE_TLS: bool = True
    SMTP_FROM_ADDRESS: str = "alerts@sentinel.local"

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, value: object) -> object:
        if isinstance(value, str) and not value.startswith("["):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
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
