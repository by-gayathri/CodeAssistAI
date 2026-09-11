"""Unit tests for parser service."""

import pytest
from app.core.exceptions import ParseError
from app.services.parser_service import ParserService

VALID_JSON = """
{
  "summary": {
    "overall_score": 70,
    "risk_level": "medium",
    "overview": "Division by zero risk."
  },
  "findings": [
    {
      "category": "logic",
      "severity": "medium",
      "title": "Division by zero is not handled",
      "description": "No guard for b == 0.",
      "line_start": 2,
      "line_end": 2,
      "evidence": "return a / b",
      "suggestion": "Validate b.",
      "suggested_code": null,
      "confidence": 0.9
    }
  ]
}
"""


def test_parse_valid_json() -> None:
    parsed = ParserService().parse(VALID_JSON)
    assert parsed.summary.overall_score == 70
    assert len(parsed.findings) == 1
    assert parsed.findings[0].category.value == "logic"


def test_parse_json_inside_markdown_fence() -> None:
    raw = f"Here is the review:\n```json\n{VALID_JSON}\n```\n"
    parsed = ParserService().parse(raw)
    assert parsed.findings[0].title.startswith("Division")


def test_parse_malformed_json_raises() -> None:
    with pytest.raises(ParseError):
        ParserService().parse("not json at all")


def test_parse_invalid_schema_raises() -> None:
    with pytest.raises(ParseError):
        ParserService().parse('{"summary": {}, "findings": []}')


def test_to_findings_assigns_ids() -> None:
    parsed = ParserService().parse(VALID_JSON)
    findings = ParserService().to_findings(parsed)
    assert findings[0].finding_id == "finding-1"
