"""Lightweight static analysis for Python source (never executes code)."""

from __future__ import annotations

import ast
import re

from app.models.domain import FindingSource, Language, ReviewCategory, Severity
from app.models.responses import Finding


class StaticAnalysisService:
    """Produce findings labeled as static_analysis for supported languages."""

    def analyze(
        self,
        code: str,
        language: Language,
        *,
        start_index: int = 1,
    ) -> list[Finding]:
        if language != Language.PYTHON:
            return []

        findings: list[Finding] = []
        findings.extend(self._syntax_findings(code, start_index=start_index))
        findings.extend(self._pattern_findings(code, start_index=start_index + len(findings)))
        return findings

    def _syntax_findings(self, code: str, *, start_index: int) -> list[Finding]:
        try:
            ast.parse(code)
            return []
        except SyntaxError as exc:
            line = exc.lineno or 1
            return [
                Finding(
                    finding_id=f"finding-{start_index}",
                    category=ReviewCategory.CODE_QUALITY,
                    severity=Severity.HIGH,
                    title="Python syntax error",
                    description=exc.msg or "Submitted code is not valid Python syntax.",
                    line_start=line,
                    line_end=line,
                    evidence=exc.text.strip() if exc.text else None,
                    suggestion="Fix the syntax error before requesting a deeper review.",
                    suggested_code=None,
                    confidence=1.0,
                    source=FindingSource.STATIC_ANALYSIS,
                )
            ]

    def _pattern_findings(self, code: str, *, start_index: int) -> list[Finding]:
        findings: list[Finding] = []
        lines = code.splitlines()
        index = start_index

        try:
            tree = ast.parse(code)
        except SyntaxError:
            return findings

        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler) and node.type is None:
                findings.append(
                    self._make(
                        index=index,
                        category=ReviewCategory.CODE_QUALITY,
                        severity=Severity.MEDIUM,
                        title="Bare except clause",
                        description=(
                            "A bare except catches all exceptions, including KeyboardInterrupt "
                            "and SystemExit, which can hide failures."
                        ),
                        line_start=getattr(node, "lineno", None),
                        evidence="except:",
                        suggestion="Catch specific exception types.",
                        confidence=0.95,
                    )
                )
                index += 1

        secret_re = re.compile(
            r"(?i)(api[_-]?key|password|secret|token)\s*=\s*['\"][^'\"]{4,}['\"]"
        )
        for line_no, line in enumerate(lines, start=1):
            if secret_re.search(line):
                findings.append(
                    self._make(
                        index=index,
                        category=ReviewCategory.SECURITY,
                        severity=Severity.HIGH,
                        title="Hardcoded credential-like literal",
                        description=(
                            "A literal assignment resembles a hardcoded secret. "
                            "Prefer environment variables or a secret manager."
                        ),
                        line_start=line_no,
                        evidence=line.strip(),
                        suggestion="Load secrets from the environment.",
                        confidence=0.85,
                    )
                )
                index += 1

        return findings

    @staticmethod
    def _make(
        *,
        index: int,
        category: ReviewCategory,
        severity: Severity,
        title: str,
        description: str,
        line_start: int | None,
        evidence: str | None,
        suggestion: str,
        confidence: float,
    ) -> Finding:
        return Finding(
            finding_id=f"finding-{index}",
            category=category,
            severity=severity,
            title=title,
            description=description,
            line_start=line_start,
            line_end=line_start,
            evidence=evidence,
            suggestion=suggestion,
            suggested_code=None,
            confidence=confidence,
            source=FindingSource.STATIC_ANALYSIS,
        )
