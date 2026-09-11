"""Parse and validate model review output."""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, Field, ValidationError, field_validator

from app.core.exceptions import ParseError
from app.models.domain import FindingSource, ReviewCategory, Severity
from app.models.responses import Finding, ReviewSummary


class ParsedFinding(BaseModel):
    category: ReviewCategory
    severity: Severity
    title: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    line_start: int | None = Field(default=None, ge=1)
    line_end: int | None = Field(default=None, ge=1)
    evidence: str | None = None
    suggestion: str | None = None
    suggested_code: str | None = None
    confidence: float = Field(..., ge=0.0, le=1.0)

    @field_validator("line_end")
    @classmethod
    def line_end_gte_start(cls, value: int | None, info: Any) -> int | None:
        start = info.data.get("line_start")
        if value is not None and start is not None and value < start:
            raise ValueError("line_end must be >= line_start")
        return value


class ParsedReviewOutput(BaseModel):
    summary: ReviewSummary
    findings: list[ParsedFinding] = Field(default_factory=list)


class ParserService:
    """Extract JSON from model output and validate against the review schema."""

    def parse(self, raw: str) -> ParsedReviewOutput:
        if not raw or not raw.strip():
            raise ParseError("Model returned empty output")

        candidate = self._extract_json_object(raw)
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError as exc:
            raise ParseError(f"Model output is not valid JSON: {exc}") from exc

        try:
            return ParsedReviewOutput.model_validate(data)
        except ValidationError as exc:
            raise ParseError(f"Model JSON failed schema validation: {exc}") from exc

    def to_findings(
        self,
        parsed: ParsedReviewOutput,
        *,
        source: FindingSource = FindingSource.LLM,
    ) -> list[Finding]:
        findings: list[Finding] = []
        for index, item in enumerate(parsed.findings, start=1):
            findings.append(
                Finding(
                    finding_id=f"finding-{index}",
                    category=item.category,
                    severity=item.severity,
                    title=item.title,
                    description=item.description,
                    line_start=item.line_start,
                    line_end=item.line_end,
                    evidence=item.evidence,
                    suggestion=item.suggestion,
                    suggested_code=item.suggested_code,
                    confidence=item.confidence,
                    source=source,
                )
            )
        return findings

    @staticmethod
    def _extract_json_object(raw: str) -> str:
        text = raw.strip()
        fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
        if fence:
            return fence.group(1).strip()

        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ParseError("Could not locate a JSON object in model output")
        return text[start : end + 1]
