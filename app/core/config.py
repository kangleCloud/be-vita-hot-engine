"""Application settings."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Centralized application settings."""

    app_name: str = Field(default="be-vita-hot-engine", description="Service name.")
    app_env: str = Field(default="develop", description="Runtime environment.")
    app_host: str = Field(default="0.0.0.0", description="Listen host.")
    app_port: int = Field(default=8000, description="Listen port.")
    hot_api_token: str = Field(default="", description="Bearer token for internal API access.")
    hot_http_timeout: float = Field(default=8.0, description="Upstream request timeout in seconds.")

    model_config = SettingsConfigDict(
        env_file=(".env", ".env.develop", ".env.production"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached settings instance."""

    return Settings()
