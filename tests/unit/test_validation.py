"""Unit tests for request validation and schemas."""

import pytest
from app.models.domain import Language, ReviewCategory, Severity
from app.models.requests import FeedbackRequest, ReviewRequest
from app.models.responses import Finding, ReviewSummary
from pydantic import ValidationError


def test_review_request_rejects_empty_code() -> None:
    with pytest.raises(ValidationError):
        ReviewRequest(code="   ", language=Language.PYTHON)


def test_review_request_accepts_valid_payload() -> None:
    req = ReviewRequest(
        code="def add(a, b):\n    return a + b\n",
        language=Language.PYTHON,
        review_types=[ReviewCategory.LOGIC],
        severity_threshold=Severity.LOW,
    )
    assert req.language == Language.PYTHON
    assert req.review_types == [ReviewCategory.LOGIC]


def test_review_request_dedupes_review_types() -> None:
    req = ReviewRequest(
        code="x = 1",
        language=Language.PYTHON,
        review_types=[ReviewCategory.LOGIC, ReviewCategory.LOGIC],
    )
    assert req.review_types == [ReviewCategory.LOGIC]


def test_feedback_request_requires_type() -> None:
    with pytest.raises(ValidationError):
        FeedbackRequest.model_validate({"comment": "hi"})


def test_finding_schema_bounds() -> None:
    with pytest.raises(ValidationError):
        Finding(
            finding_id="finding-1",
            category=ReviewCategory.LOGIC,
            severity=Severity.LOW,
            title="t",
            description="d",
            confidence=1.5,
        )


def test_summary_score_bounds() -> None:
    with pytest.raises(ValidationError):
        ReviewSummary(overall_score=120, risk_level=Severity.LOW, overview="x")
