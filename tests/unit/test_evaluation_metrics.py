"""Unit tests for evaluation metrics."""

from app.models.domain import ReviewCategory, Severity
from app.models.responses import Finding
from evaluation.metrics import (
    CaseResult,
    compute_metrics,
    count_duplicates,
    finding_matches_expectation,
    jaccard,
)


def test_jaccard_similarity() -> None:
    assert jaccard("division by zero", "division by zero risk") > 0.3
    assert jaccard("alpha", "beta") == 0.0


def test_finding_matches_expectation() -> None:
    finding = Finding(
        finding_id="finding-1",
        category=ReviewCategory.LOGIC,
        severity=Severity.MEDIUM,
        title="Division by zero is not handled",
        description="No guard for divisor.",
        confidence=0.9,
    )
    assert finding_matches_expectation(
        finding,
        expected_categories=["logic"],
        expected_severity="medium",
        expected_issue_description="Division by zero is not handled",
    )


def test_compute_metrics_basic() -> None:
    results = [
        CaseResult(
            case_id="a",
            matched=True,
            expected_categories=["logic"],
            predicted_categories=["logic"],
            json_valid=True,
            latency_ms=10,
            provider_failed=False,
            finding_count=1,
            duplicate_count=0,
            severity_agreed=True,
        ),
        CaseResult(
            case_id="b",
            matched=True,
            expected_categories=[],
            predicted_categories=[],
            json_valid=True,
            latency_ms=5,
            provider_failed=False,
            finding_count=0,
            duplicate_count=0,
            severity_agreed=None,
        ),
    ]
    report = compute_metrics(results)
    assert report.json_validity_rate == 1.0
    assert report.provider_failure_rate == 0.0
    assert report.precision > 0


def test_count_duplicates() -> None:
    findings = [
        Finding(
            finding_id="1",
            category=ReviewCategory.LOGIC,
            severity=Severity.LOW,
            title="Same",
            description="a",
            line_start=1,
            confidence=0.5,
        ),
        Finding(
            finding_id="2",
            category=ReviewCategory.LOGIC,
            severity=Severity.LOW,
            title="Same",
            description="b",
            line_start=1,
            confidence=0.5,
        ),
    ]
    assert count_duplicates(findings) == 1
