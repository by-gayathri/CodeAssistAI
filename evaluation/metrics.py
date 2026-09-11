"""Evaluation metrics and matching helpers.

Matching strategy
-----------------
A generated finding matches an expected case when:
1. The finding category is in the case's expected_categories (if any), AND
2. Either the finding severity rank is within one level of expected_severity,
   OR the finding title/description shares a token overlap with the expected
   issue description (Jaccard similarity >= 0.15 on normalized tokens).

Cases with empty expected_categories are treated as "clean" samples: a true
positive occurs when the system returns zero findings; any finding is a false
positive for that case.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.models.domain import SEVERITY_RANK, Severity
from app.models.responses import Finding


def _tokenize(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", text.lower()) if len(t) > 2}


def jaccard(a: str, b: str) -> float:
    ta, tb = _tokenize(a), _tokenize(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def severity_close(actual: Severity, expected: Severity, *, max_distance: int = 1) -> bool:
    return abs(SEVERITY_RANK[actual] - SEVERITY_RANK[expected]) <= max_distance


def finding_matches_expectation(
    finding: Finding,
    *,
    expected_categories: list[str],
    expected_severity: str,
    expected_issue_description: str,
) -> bool:
    if expected_categories and finding.category.value not in expected_categories:
        return False

    expected_sev = Severity(expected_severity)
    semantic = jaccard(
        f"{finding.title} {finding.description}",
        expected_issue_description,
    )
    return severity_close(finding.severity, expected_sev) or semantic >= 0.15


@dataclass
class CaseResult:
    case_id: str
    matched: bool
    expected_categories: list[str]
    predicted_categories: list[str]
    json_valid: bool
    latency_ms: float
    provider_failed: bool
    finding_count: int
    duplicate_count: int
    severity_agreed: bool | None = None


@dataclass
class MetricsReport:
    cases: list[CaseResult] = field(default_factory=list)
    precision: float = 0.0
    recall: float = 0.0
    category_accuracy: float = 0.0
    severity_agreement: float = 0.0
    duplicate_finding_rate: float = 0.0
    json_validity_rate: float = 0.0
    average_latency_ms: float = 0.0
    provider_failure_rate: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "metrics": {
                "precision": self.precision,
                "recall": self.recall,
                "category_accuracy": self.category_accuracy,
                "severity_agreement": self.severity_agreement,
                "duplicate_finding_rate": self.duplicate_finding_rate,
                "json_validity_rate": self.json_validity_rate,
                "average_latency_ms": self.average_latency_ms,
                "provider_failure_rate": self.provider_failure_rate,
            },
            "cases": [
                {
                    "case_id": c.case_id,
                    "matched": c.matched,
                    "expected_categories": c.expected_categories,
                    "predicted_categories": c.predicted_categories,
                    "json_valid": c.json_valid,
                    "latency_ms": c.latency_ms,
                    "provider_failed": c.provider_failed,
                    "finding_count": c.finding_count,
                    "duplicate_count": c.duplicate_count,
                    "severity_agreed": c.severity_agreed,
                }
                for c in self.cases
            ],
        }


def compute_metrics(case_results: list[CaseResult]) -> MetricsReport:
    report = MetricsReport(cases=case_results)
    if not case_results:
        return report

    # Precision / recall over cases that expect at least one category.
    issue_cases = [c for c in case_results if c.expected_categories]
    clean_cases = [c for c in case_results if not c.expected_categories]

    true_positives = sum(1 for c in issue_cases if c.matched and c.finding_count > 0)
    false_negatives = sum(1 for c in issue_cases if not c.matched)
    false_positives = sum(1 for c in clean_cases if c.finding_count > 0)
    false_positives += sum(1 for c in issue_cases if c.finding_count > 0 and not c.matched)

    pred_positive = true_positives + false_positives
    report.precision = true_positives / pred_positive if pred_positive else 0.0
    denom_recall = true_positives + false_negatives
    report.recall = true_positives / denom_recall if denom_recall else 0.0

    category_hits = 0
    category_total = 0
    severity_hits = 0
    severity_total = 0
    for case in case_results:
        if not case.expected_categories:
            category_total += 1
            if case.finding_count == 0:
                category_hits += 1
            continue
        category_total += 1
        if any(cat in case.expected_categories for cat in case.predicted_categories):
            category_hits += 1
        if case.severity_agreed is not None:
            severity_total += 1
            if case.severity_agreed:
                severity_hits += 1

    report.category_accuracy = category_hits / category_total if category_total else 0.0
    report.severity_agreement = severity_hits / severity_total if severity_total else 0.0

    total_findings = sum(c.finding_count for c in case_results)
    total_dupes = sum(c.duplicate_count for c in case_results)
    report.duplicate_finding_rate = total_dupes / total_findings if total_findings else 0.0
    report.json_validity_rate = sum(1 for c in case_results if c.json_valid) / len(case_results)
    report.average_latency_ms = sum(c.latency_ms for c in case_results) / len(case_results)
    report.provider_failure_rate = sum(1 for c in case_results if c.provider_failed) / len(
        case_results
    )
    return report


def count_duplicates(findings: list[Finding]) -> int:
    seen: set[tuple[str, str, int | None]] = set()
    dupes = 0
    for finding in findings:
        key = (finding.title.lower(), finding.category.value, finding.line_start)
        if key in seen:
            dupes += 1
        else:
            seen.add(key)
    return dupes
