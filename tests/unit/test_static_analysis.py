"""Unit tests for static analysis."""

from app.models.domain import FindingSource, Language
from app.services.static_analysis_service import StaticAnalysisService


def test_static_analysis_syntax_error() -> None:
    findings = StaticAnalysisService().analyze("def broken(:\n", Language.PYTHON)
    assert findings
    assert findings[0].source == FindingSource.STATIC_ANALYSIS
    assert "syntax" in findings[0].title.lower()


def test_static_analysis_bare_except() -> None:
    code = "try:\n    x = 1\nexcept:\n    pass\n"
    findings = StaticAnalysisService().analyze(code, Language.PYTHON)
    assert any("Bare except" in f.title for f in findings)


def test_static_analysis_skips_non_python() -> None:
    findings = StaticAnalysisService().analyze("function x() {}", Language.JAVASCRIPT)
    assert findings == []
