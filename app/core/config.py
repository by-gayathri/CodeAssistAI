"""Application settings loaded from environment variables."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ProviderName = Literal["mock", "transformer", "external"]


class Settings(BaseSettings):
    """Runtime configuration for CodeAssistAI."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "codeassistai"
    app_version: str = "1.0.0"
    log_level: str = "INFO"

    provider: ProviderName = "mock"
    max_code_length: int = Field(default=50_000, ge=1)

    transformer_model_name: str = "Salesforce/codegen-350M-mono"
    transformer_max_new_tokens: int = Field(default=512, ge=1)
    transformer_temperature: float = Field(default=0.2, ge=0.0)
    transformer_device: str = "cpu"

    external_llm_api_key: SecretStr | None = None
    external_llm_base_url: str = "https://api.openai.com/v1"
    external_llm_model: str = "gpt-4o-mini"
    external_llm_timeout_seconds: float = Field(default=60.0, gt=0)


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
