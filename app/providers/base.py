"""Provider protocol and factory."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.core.config import Settings, get_settings
from app.core.exceptions import ProviderError


@runtime_checkable
class ReviewModelProvider(Protocol):
    """Abstraction over LLM / transformer backends used for code review."""

    @property
    def name(self) -> str:
        """Provider identifier used in response metadata."""
        ...

    @property
    def model_name(self) -> str:
        """Underlying model identifier used in response metadata."""
        ...

    def generate_review(self, code: str, language: str, prompt: str) -> str:
        """Generate a raw review string (expected to contain JSON)."""
        ...


def create_provider(settings: Settings | None = None) -> ReviewModelProvider:
    """Instantiate the configured review provider."""
    cfg = settings or get_settings()
    if cfg.provider == "mock":
        from app.providers.mock_provider import MockProvider

        return MockProvider()
    if cfg.provider == "transformer":
        from app.providers.transformer_provider import TransformerProvider

        return TransformerProvider(settings=cfg)
    if cfg.provider == "external":
        from app.providers.external_llm_provider import ExternalLLMProvider

        return ExternalLLMProvider(settings=cfg)
    raise ProviderError(f"Unsupported provider: {cfg.provider}")
