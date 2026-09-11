"""Unit tests for mock provider and provider factory."""

import json

from app.core.config import Settings
from app.providers.base import create_provider
from app.providers.mock_provider import MockProvider


def test_mock_provider_detects_division_by_zero() -> None:
    provider = MockProvider()
    raw = provider.generate_review(
        "def divide(a, b):\n    return a / b\n",
        "python",
        "prompt",
    )
    data = json.loads(raw)
    titles = [f["title"] for f in data["findings"]]
    assert any("Division by zero" in t for t in titles)
    assert data["summary"]["overall_score"] <= 100


def test_mock_provider_detects_hardcoded_secret() -> None:
    provider = MockProvider()
    raw = provider.generate_review(
        'api_key = "sk-secret-value-1234"\n',
        "python",
        "prompt",
    )
    data = json.loads(raw)
    assert any(f["category"] == "security" for f in data["findings"])


def test_create_provider_defaults_to_mock() -> None:
    provider = create_provider(Settings(provider="mock"))
    assert provider.name == "mock"
