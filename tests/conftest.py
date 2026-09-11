"""Shared pytest fixtures."""

from __future__ import annotations

import pytest
from app.core.config import Settings
from app.main import create_app
from app.providers.mock_provider import MockProvider
from app.repositories.memory_repository import MemoryReviewRepository
from fastapi.testclient import TestClient


@pytest.fixture
def settings() -> Settings:
    return Settings(provider="mock", max_code_length=1000)


@pytest.fixture
def mock_provider() -> MockProvider:
    return MockProvider()


@pytest.fixture
def repository() -> MemoryReviewRepository:
    repo = MemoryReviewRepository()
    yield repo
    repo.clear()


@pytest.fixture
def client(settings: Settings, mock_provider: MockProvider, repository: MemoryReviewRepository):
    application = create_app()
    application.state.settings = settings
    application.state.provider = mock_provider
    application.state.repository = repository
    with TestClient(application) as test_client:
        yield test_client
