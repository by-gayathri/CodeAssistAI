"""Run the CodeAssistAI evaluation pipeline.

Usage:
    python -m evaluation.run_evaluation
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

from app.core.config import Settings
from app.core.exceptions import ParseError, ProviderError
from app.models.domain import Language, ReviewCategory, Severity
from app.models.requests import ReviewRequest
from app.providers.base import create_provider
from app.repositories.memory_repository import MemoryReviewRepository
from app.services.review_service import ReviewService

from evaluation.metrics import (
    CaseResult,
    compute_metrics,
    count_duplicates,
    finding_matches_expectation,
    severity_close,
)

DATASET_PATH = Path(__file__).resolve().parent / "datasets" / "cases.json"
DEFAULT_OUTPUT = Path(__file__).resolve().parent / "results" / "latest.json"


def load_dataset(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, list):
        raise ValueError("Dataset must be a JSON array")
    return data


def evaluate_case(service: ReviewService, case: dict[str, Any]) -> CaseResult:
    expected_categories = list(case.get("expected_categories") or [])
    expected_severity = case.get("expected_severity", "low")
    expected_description = case.get("expected_issue_description", "")

    started = time.perf_counter()
    json_valid = False
    provider_failed = False
    findings = []
    try:
        review_types = (
            [ReviewCategory(c) for c in expected_categories]
            if expected_categories
            else list(ReviewCategory)
        )
        # Always allow full category set so mock/static can surface related issues.
        review_types = list(ReviewCategory)
        response = service.create_review(
            ReviewRequest(
                code=case["code"],
                language=Language(case["language"]),
                review_types=review_types,
                severity_threshold=Severity.LOW,
                include_summary=True,
            )
        )
        findings = response.findings
        json_valid = True
        latency_ms = response.metadata.duration_ms
    except (ProviderError, ParseError):
        provider_failed = True
        latency_ms = (time.perf_counter() - started) * 1000
    except Exception:
        provider_failed = True
        latency_ms = (time.perf_counter() - started) * 1000

    predicted_categories = sorted({f.category.value for f in findings})
    duplicate_count = count_duplicates(findings)

    if not expected_categories:
        matched = len(findings) == 0
        severity_agreed = None
    else:
        matched = any(
            finding_matches_expectation(
                finding,
                expected_categories=expected_categories,
                expected_severity=expected_severity,
                expected_issue_description=expected_description,
            )
            for finding in findings
        )
        severity_agreed = any(
            severity_close(f.severity, Severity(expected_severity)) for f in findings
        )

    return CaseResult(
        case_id=case["id"],
        matched=matched,
        expected_categories=expected_categories,
        predicted_categories=predicted_categories,
        json_valid=json_valid,
        latency_ms=float(latency_ms),
        provider_failed=provider_failed,
        finding_count=len(findings),
        duplicate_count=duplicate_count,
        severity_agreed=severity_agreed,
    )


def run_evaluation(
    *,
    dataset_path: Path = DATASET_PATH,
    output_path: Path | None = DEFAULT_OUTPUT,
    provider_name: str = "mock",
) -> dict[str, Any]:
    settings = Settings(provider=provider_name)  # type: ignore[arg-type]
    service = ReviewService(
        provider=create_provider(settings),
        repository=MemoryReviewRepository(),
        settings=settings,
    )
    cases = load_dataset(dataset_path)
    results = [evaluate_case(service, case) for case in cases]
    report = compute_metrics(results)
    payload = report.to_dict()
    payload["dataset"] = str(dataset_path)
    payload["provider"] = provider_name
    payload["case_count"] = len(cases)

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    return payload


def _print_human(payload: dict[str, Any]) -> None:
    metrics = payload["metrics"]
    print("CodeAssistAI evaluation results")
    print(f"Provider: {payload['provider']}")
    print(f"Cases: {payload['case_count']}")
    print("---")
    for key, value in metrics.items():
        if isinstance(value, float):
            print(f"{key}: {value:.4f}")
        else:
            print(f"{key}: {value}")
    print("---")
    for case in payload["cases"]:
        status = "MATCH" if case["matched"] else "MISS"
        print(
            f"{case['case_id']}: {status} "
            f"(findings={case['finding_count']}, latency_ms={case['latency_ms']:.1f})"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run CodeAssistAI evaluation")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DATASET_PATH,
        help="Path to evaluation dataset JSON",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Path for machine-readable JSON report",
    )
    parser.add_argument(
        "--provider",
        default="mock",
        choices=["mock", "transformer", "external"],
        help="Provider to evaluate (default: mock)",
    )
    args = parser.parse_args(argv)

    payload = run_evaluation(
        dataset_path=args.dataset,
        output_path=args.output,
        provider_name=args.provider,
    )
    _print_human(payload)
    if args.output:
        print(f"\nWrote JSON report to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
