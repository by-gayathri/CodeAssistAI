"""Deterministic mock provider for local development and tests."""

from __future__ import annotations

import json
import re
from typing import Any


class MockProvider:
    """Return deterministic structured review JSON based on simple heuristics."""

    name = "mock"
    model_name = "mock-deterministic-v1"

    def generate_review(self, code: str, language: str, prompt: str) -> str:
        findings = self._detect_findings(code, language)
        summary = self._build_summary(findings)
        payload = {"summary": summary, "findings": findings}
        return json.dumps(payload)

    def _detect_findings(self, code: str, language: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        lines = code.splitlines()

        for idx, line in enumerate(lines, start=1):
            stripped = line.strip()
            if re.search(r"/\s*b\b|/\s*[a-zA-Z_]\w*\b", stripped) and "ZeroDivision" not in code:
                if re.search(r"return\s+.+/", stripped) or re.search(r"=\s*.+/", stripped):
                    if "/ 0" in stripped or re.search(r"/\s*[a-zA-Z_]\w*", stripped):
                        if self._looks_like_division(stripped):
                            findings.append(
                                self._finding(
                                    category="logic",
                                    severity="medium",
                                    title="Division by zero is not handled",
                                    description=(
                                        "The expression performs division without validating "
                                        "that the divisor is non-zero."
                                    ),
                                    line_start=idx,
                                    line_end=idx,
                                    evidence=stripped,
                                    suggestion="Validate the divisor before dividing.",
                                    suggested_code=(
                                        "if b == 0:\n"
                                        "    raise ValueError('b must not be zero')\n"
                                        "return a / b"
                                    ),
                                    confidence=0.94,
                                )
                            )
                            break

        if re.search(r"except\s*:", code) or re.search(r"except\s+Exception\s*:", code):
            line_no = self._first_match_line(lines, r"except\s*(:|Exception\s*:)")
            findings.append(
                self._finding(
                    category="code_quality",
                    severity="medium",
                    title="Broad exception handling",
                    description=(
                        "Catching bare Exception or using a bare except hides unexpected "
                        "failures and complicates debugging."
                    ),
                    line_start=line_no,
                    line_end=line_no,
                    evidence=lines[line_no - 1].strip() if line_no else "except:",
                    suggestion="Catch specific exception types and re-raise unexpected errors.",
                    suggested_code="except ValueError as exc:\n    logger.warning('%s', exc)",
                    confidence=0.9,
                )
            )

        if re.search(
            r"(api[_-]?key|password|secret|token)\s*=\s*['\"][^'\"]+['\"]",
            code,
            re.IGNORECASE,
        ):
            line_no = self._first_match_line(
                lines,
                r"(api[_-]?key|password|secret|token)\s*=\s*['\"][^'\"]+['\"]",
            )
            findings.append(
                self._finding(
                    category="security",
                    severity="high",
                    title="Hardcoded credential detected",
                    description=(
                        "A secret-like value appears to be hardcoded. Credentials should be "
                        "loaded from environment variables or a secret manager."
                    ),
                    line_start=line_no,
                    line_end=line_no,
                    evidence=lines[line_no - 1].strip() if line_no else None,
                    suggestion="Move secrets to environment variables.",
                    suggested_code="api_key = os.environ['API_KEY']",
                    confidence=0.92,
                )
            )

        if re.search(r"(execute|cursor\.execute)\s*\(\s*[f\"'].*%s|SELECT\s+.+\s*\+", code, re.I):
            line_no = self._first_match_line(lines, r"(execute|SELECT\s+.+\s*\+|f[\"'].*SELECT)")
            findings.append(
                self._finding(
                    category="security",
                    severity="critical",
                    title="Possible SQL injection pattern",
                    description=(
                        "SQL appears to be constructed via string formatting or concatenation, "
                        "which can enable injection."
                    ),
                    line_start=line_no,
                    line_end=line_no,
                    evidence=lines[line_no - 1].strip() if line_no else None,
                    suggestion="Use parameterized queries / bound parameters.",
                    suggested_code='cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))',
                    confidence=0.88,
                )
            )

        unused = re.search(r"\b([a-z_][a-z0-9_]*)\s*=\s*.+", code)
        if unused and language == "python":
            name = unused.group(1)
            if name not in {"_", "self"} and code.count(name) == 1:
                line_no = self._first_match_line(lines, rf"\b{re.escape(name)}\s*=")
                findings.append(
                    self._finding(
                        category="readability",
                        severity="low",
                        title=f"Possibly unused variable '{name}'",
                        description=(
                            f"Variable '{name}' is assigned but not referenced elsewhere "
                            "in the snippet."
                        ),
                        line_start=line_no,
                        line_end=line_no,
                        evidence=lines[line_no - 1].strip() if line_no else name,
                        suggestion="Remove the unused assignment or use the value.",
                        suggested_code=None,
                        confidence=0.7,
                    )
                )

        # Only suggest missing tests for non-trivial snippets that already have
        # other issues, or that contain branching / I/O / auth-like logic.
        nontrivial = bool(re.search(r"\b(if|for|while|try|open\(|authenticate)\b", code))
        if (
            (findings or nontrivial)
            and "def " in code
            and "test_" not in code
            and "assert " not in code
        ):
            if re.search(r"def\s+\w+\(", code):
                findings.append(
                    self._finding(
                        category="testing",
                        severity="low",
                        title="Missing tests for submitted code",
                        description=(
                            "The snippet defines callable logic but does not include tests "
                            "covering success or failure paths."
                        ),
                        line_start=1,
                        line_end=1,
                        evidence=None,
                        suggestion="Add unit tests for happy path and edge cases.",
                        suggested_code=None,
                        confidence=0.65,
                    )
                )

        # Deduplicate by title within mock output
        seen: set[str] = set()
        unique: list[dict[str, Any]] = []
        for item in findings:
            if item["title"] in seen:
                continue
            seen.add(item["title"])
            unique.append(item)
        return unique

    def _build_summary(self, findings: list[dict[str, Any]]) -> dict[str, Any]:
        if not findings:
            return {
                "overall_score": 95,
                "risk_level": "low",
                "overview": "No significant issues were detected in the submitted code.",
            }

        severity_order = {"low": 1, "medium": 2, "high": 3, "critical": 4}
        max_sev = max(findings, key=lambda f: severity_order[f["severity"]])["severity"]
        score = max(20, 100 - 12 * len(findings) - 5 * severity_order[max_sev])
        overview = findings[0]["description"]
        return {
            "overall_score": score,
            "risk_level": max_sev,
            "overview": overview,
        }

    @staticmethod
    def _finding(
        *,
        category: str,
        severity: str,
        title: str,
        description: str,
        line_start: int | None,
        line_end: int | None,
        evidence: str | None,
        suggestion: str | None,
        suggested_code: str | None,
        confidence: float,
    ) -> dict[str, Any]:
        return {
            "category": category,
            "severity": severity,
            "title": title,
            "description": description,
            "line_start": line_start,
            "line_end": line_end,
            "evidence": evidence,
            "suggestion": suggestion,
            "suggested_code": suggested_code,
            "confidence": confidence,
        }

    @staticmethod
    def _looks_like_division(line: str) -> bool:
        return bool(re.search(r"[^/=!<>]=.*/|return\s+.*/", line)) and "//" not in line

    @staticmethod
    def _first_match_line(lines: list[str], pattern: str) -> int | None:
        regex = re.compile(pattern, re.IGNORECASE)
        for idx, line in enumerate(lines, start=1):
            if regex.search(line):
                return idx
        return 1
