"""FastAPI dependency providers."""

from __future__ import annotations

from functools import lru_cache

from fastapi import Request

from app.core.config import Settings, get_settings
from app.providers.base import ReviewModelProvider, create_provider
from app.repositories.memory_repository import MemoryReviewRepository
from app.services.review_service import ReviewService


@lru_cache
def get_repository() -> MemoryReviewRepository:
    return MemoryReviewRepository()


@lru_cache
def get_provider() -> ReviewModelProvider:
    return create_provider(get_settings())


def get_review_service(request: Request) -> ReviewService:
    """Resolve ReviewService, allowing app.state overrides in tests."""
    provider = getattr(request.app.state, "provider", None) or get_provider()
    repository = getattr(request.app.state, "repository", None) or get_repository()
    settings: Settings = getattr(request.app.state, "settings", None) or get_settings()
    return ReviewService(provider=provider, repository=repository, settings=settings)
