"""
Centralized, typed application configuration.

Production services never hardcode secrets or environment-specific
values (DB paths, token lifetimes, secret keys) directly in code -
those live in environment variables (injected by Docker, Kubernetes,
CI/CD, etc.) and are loaded once, validated, and shared everywhere via
a single `Settings` object.

`pydantic-settings` gives us:
    - Type validation (fail fast at startup if config is wrong, not
      halfway through handling a request).
    - A single source of truth (`get_settings()`) instead of scattered
      `os.environ["X"]` calls throughout the codebase.
    - Easy overriding in tests (construct a `Settings(...)` directly).
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All runtime configuration for the auth service.

    Values are read from environment variables of the same name (case
    insensitive), falling back to the defaults below if unset. See
    `.env.example` for the full list an operator can override.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    APP_NAME: str = "auth-service"
    ENVIRONMENT: str = "development"  # "development" | "staging" | "production"
    LOG_LEVEL: str = "INFO"

    # Where user records are persisted. Defaults to a local SQLite file so
    # the service runs with zero external dependencies out of the box;
    # in real production this would point at Postgres instead.
    DATABASE_URL: str = "sqlite+aiosqlite:///./auth.db"

    # JWT signing. SECRET_KEY MUST be overridden via env var in any real
    # deployment - the default here only exists so local dev works instantly.
    SECRET_KEY: str = "insecure-dev-secret-change-me"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide Settings singleton.

    `lru_cache` means the environment is only parsed/validated once per
    process, and every part of the app that calls this gets the exact
    same object - not a fresh, possibly-inconsistent copy.
    """
    return Settings()