"""Orchestrate code review generation."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from uuid import uuid4

from app.core.config import Settings, get_settings
from app.core.exceptions import ParseError, ProviderError, ValidationAppError
from app.core.logging import get_logger, log_event
from app.models.domain import (
    FindingSource,
    ReviewCategory,
    ReviewStatus,
    Severity,
    severity_meets_threshold,
)
from app.models.requests import FeedbackRequest, ReviewRequest
from app.models.responses import (
    FeedbackResponse,
    Finding,
    ReviewMetadata,
    ReviewResponse,
    ReviewSummary,
)
from app.providers.base import ReviewModelProvider
from app.repositories.base import ReviewRepository
from app.services.parser_service import ParserService
from app.services.prompt_service import PromptService
from app.services.static_analysis_service import StaticAnalysisService

logger = get_logger(__name__)


class ReviewService:
    """Coordinate prompts, providers, parsing, static analysis, and persistence."""

    def __init__(
        self,
        *,
        provider: ReviewModelProvider,
        repository: ReviewRepository,
        prompt_service: PromptService | None = None,
        parser_service: ParserService | None = None,
        static_analysis: StaticAnalysisService | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._provider = provider
        self._repository = repository
        self._prompts = prompt_service or PromptService()
        self._parser = parser_service or ParserService()
        self._static = static_analysis or StaticAnalysisService()
        self._settings = settings or get_settings()

    def create_review(self, request: ReviewRequest) -> ReviewResponse:
        if len(request.code) > self._settings.max_code_length:
            raise ValidationAppError(
                f"code exceeds maximum length of {self._settings.max_code_length} characters"
            )

        review_id = f"review-{uuid4().hex[:12]}"
        log_event(
            logger,
            "review_request_received",
            review_id=review_id,
            language=request.language.value,
            provider=self._provider.name,
            code_length=len(request.code),
        )
        log_event(logger, "provider_selected", review_id=review_id, provider=self._provider.name)

        started = time.perf_counter()
        try:
            prompt = self._prompts.build_full_prompt(
                code=request.code,
                language=request.language.value,
                file_name=request.file_name,
                review_types=request.review_types,
                severity_threshold=request.severity_threshold,
            )
            raw = self._provider.generate_review(request.code, request.language.value, prompt)
            parsed = self._parser.parse(raw)
            llm_findings = self._parser.to_findings(parsed, source=FindingSource.LLM)
        except (ProviderError, ParseError) as exc:
            duration_ms = int((time.perf_counter() - started) * 1000)
            log_event(
                logger,
                "review_failed",
                review_id=review_id,
                error=exc.code,
                duration_ms=duration_ms,
            )
            raise

        static_findings = self._static.analyze(
            request.code,
            request.language,
            start_index=len(llm_findings) + 1,
        )
        merged = self._merge_findings(llm_findings, static_findings)
        filtered = self._filter_by_severity(merged, request.severity_threshold)
        filtered = self._filter_by_categories(filtered, request.review_types)
        deduped = self._deduplicate(filtered)
        self._reindex(deduped)

        summary = None
        if request.include_summary:
            summary = self._maybe_adjust_summary(parsed.summary, deduped)

        duration_ms = int((time.perf_counter() - started) * 1000)
        response = ReviewResponse(
            review_id=review_id,
            status=ReviewStatus.COMPLETED,
            language=request.language,
            summary=summary,
            findings=deduped,
            metadata=ReviewMetadata(
                provider=self._provider.name,
                model=self._provider.model_name,
                duration_ms=duration_ms,
                created_at=datetime.now(UTC),
            ),
        )
        self._repository.save_review(response)
        log_event(
            logger,
            "review_completed",
            review_id=review_id,
            duration_ms=duration_ms,
            findings=len(deduped),
            provider=self._provider.name,
        )
        return response

    def get_review(self, review_id: str) -> ReviewResponse | None:
        return self._repository.get_review(review_id)

    def add_feedback(self, review_id: str, request: FeedbackRequest) -> FeedbackResponse:
        return self._repository.save_feedback(
            review_id=review_id,
            finding_id=request.finding_id,
            feedback_type=request.feedback_type,
            comment=request.comment,
        )

    @staticmethod
    def _filter_by_severity(findings: list[Finding], threshold: Severity) -> list[Finding]:
        return [f for f in findings if severity_meets_threshold(f.severity, threshold)]

    @staticmethod
    def _filter_by_categories(
        findings: list[Finding], categories: list[ReviewCategory]
    ) -> list[Finding]:
        allowed = set(categories)
        return [f for f in findings if f.category in allowed]

    @staticmethod
    def _deduplicate(findings: list[Finding]) -> list[Finding]:
        seen: set[tuple[str, str, int | None]] = set()
        unique: list[Finding] = []
        for finding in findings:
            key = (finding.title.lower(), finding.category.value, finding.line_start)
            if key in seen:
                continue
            seen.add(key)
            unique.append(finding)
        return unique

    @staticmethod
    def _merge_findings(
        llm_findings: list[Finding], static_findings: list[Finding]
    ) -> list[Finding]:
        merged = list(llm_findings)
        llm_keys = {(f.title.lower(), f.category.value, f.line_start) for f in llm_findings}
        for finding in static_findings:
            key = (finding.title.lower(), finding.category.value, finding.line_start)
            if key in llm_keys:
                # Prefer hybrid when both sides flagged the same issue.
                for idx, existing in enumerate(merged):
                    existing_key = (
                        existing.title.lower(),
                        existing.category.value,
                        existing.line_start,
                    )
                    if existing_key == key:
                        merged[idx] = existing.model_copy(update={"source": FindingSource.HYBRID})
                        break
            else:
                merged.append(finding)
        return merged

    @staticmethod
    def _reindex(findings: list[Finding]) -> None:
        for index, finding in enumerate(findings, start=1):
            finding.finding_id = f"finding-{index}"

    @staticmethod
    def _maybe_adjust_summary(summary: ReviewSummary, findings: list[Finding]) -> ReviewSummary:
        if not findings:
            return summary
        rank = {Severity.LOW: 1, Severity.MEDIUM: 2, Severity.HIGH: 3, Severity.CRITICAL: 4}
        max_sev = max(findings, key=lambda f: rank[f.severity]).severity
        # Keep model overview when present; bump risk if static/LLM findings are worse.
        risk = summary.risk_level
        if rank[max_sev] > rank[risk]:
            risk = max_sev
        return ReviewSummary(
            overall_score=summary.overall_score,
            risk_level=risk,
            overview=summary.overview,
        )
