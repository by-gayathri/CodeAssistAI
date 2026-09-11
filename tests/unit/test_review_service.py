"""Unit tests for repository and review orchestration helpers."""

from datetime import UTC, datetime

import pytest
from app.core.config import Settings
from app.core.exceptions import NotFoundError, ParseError, ValidationAppError
from app.models.domain import FeedbackType, Language, ReviewCategory, ReviewStatus, Severity
from app.models.requests import ReviewRequest
from app.models.responses import Finding, ReviewMetadata, ReviewResponse, ReviewSummary
from app.providers.mock_provider import MockProvider
from app.repositories.memory_repository import MemoryReviewRepository
from app.services.review_service import ReviewService


class FailingProvider:
    name = "failing"
    model_name = "failing-model"

    def generate_review(self, code: str, language: str, prompt: str) -> str:
        return "definitely not json"


def test_memory_repository_roundtrip() -> None:
    repo = MemoryReviewRepository()
    review = ReviewResponse(
        review_id="review-1",
        status=ReviewStatus.COMPLETED,
        language=Language.PYTHON,
        summary=ReviewSummary(overall_score=80, risk_level=Severity.LOW, overview="ok"),
        findings=[],
        metadata=ReviewMetadata(
            provider="mock",
            model="m",
            duration_ms=1,
            created_at=datetime.now(UTC),
        ),
    )
    repo.save_review(review)
    assert repo.get_review("review-1") is not None
    fb = repo.save_feedback(
        review_id="review-1",
        finding_id=None,
        feedback_type=FeedbackType.USEFUL,
        comment="good",
    )
    assert fb.review_id == "review-1"
    assert len(repo.list_feedback("review-1")) == 1


def test_repository_missing_review() -> None:
    repo = MemoryReviewRepository()
    with pytest.raises(NotFoundError):
        repo.save_feedback(
            review_id="missing",
            finding_id=None,
            feedback_type=FeedbackType.USEFUL,
            comment=None,
        )


def test_review_service_create_and_filter() -> None:
    service = ReviewService(
        provider=MockProvider(),
        repository=MemoryReviewRepository(),
        settings=Settings(provider="mock", max_code_length=10_000),
    )
    response = service.create_review(
        ReviewRequest(
            code="def divide(a, b):\n    return a / b\n",
            language=Language.PYTHON,
            review_types=[
                ReviewCategory.LOGIC,
                ReviewCategory.TESTING,
                ReviewCategory.READABILITY,
                ReviewCategory.SECURITY,
                ReviewCategory.PERFORMANCE,
                ReviewCategory.CODE_QUALITY,
                ReviewCategory.MAINTAINABILITY,
            ],
            severity_threshold=Severity.LOW,
        )
    )
    assert response.status == ReviewStatus.COMPLETED
    assert response.metadata.provider == "mock"
    assert any("Division" in f.title for f in response.findings)


def test_review_service_severity_filter() -> None:
    service = ReviewService(
        provider=MockProvider(),
        repository=MemoryReviewRepository(),
        settings=Settings(provider="mock"),
    )
    response = service.create_review(
        ReviewRequest(
            code="def divide(a, b):\n    return a / b\n",
            language=Language.PYTHON,
            severity_threshold=Severity.HIGH,
            review_types=[ReviewCategory.LOGIC, ReviewCategory.TESTING],
        )
    )
    assert all(f.severity in {Severity.HIGH, Severity.CRITICAL} for f in response.findings)


def test_review_service_rejects_oversized_code() -> None:
    service = ReviewService(
        provider=MockProvider(),
        repository=MemoryReviewRepository(),
        settings=Settings(provider="mock", max_code_length=10),
    )
    with pytest.raises(ValidationAppError):
        service.create_review(ReviewRequest(code="x" * 50, language=Language.PYTHON))


def test_review_service_parse_failure() -> None:
    service = ReviewService(
        provider=FailingProvider(),
        repository=MemoryReviewRepository(),
        settings=Settings(provider="mock"),
    )
    with pytest.raises(ParseError):
        service.create_review(ReviewRequest(code="print('hi')", language=Language.PYTHON))


def test_deduplicate_findings() -> None:
    findings = [
        Finding(
            finding_id="finding-1",
            category=ReviewCategory.LOGIC,
            severity=Severity.MEDIUM,
            title="Same",
            description="a",
            line_start=1,
            confidence=0.5,
        ),
        Finding(
            finding_id="finding-2",
            category=ReviewCategory.LOGIC,
            severity=Severity.MEDIUM,
            title="Same",
            description="b",
            line_start=1,
            confidence=0.6,
        ),
    ]
    deduped = ReviewService._deduplicate(findings)
    assert len(deduped) == 1
