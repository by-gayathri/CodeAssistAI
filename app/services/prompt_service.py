"""Prompt construction from versioned templates."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.models.domain import ReviewCategory, Severity

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


class PromptService:
    """Build system and user prompts for code review."""

    def __init__(self, prompts_dir: Path | None = None) -> None:
        directory = prompts_dir or PROMPTS_DIR
        self._env = Environment(
            loader=FileSystemLoader(str(directory)),
            autoescape=select_autoescape(enabled_extensions=()),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self._system_template = self._env.get_template("system_prompt.txt")
        self._review_template = self._env.get_template("review_prompt.txt")

    def build_system_prompt(self) -> str:
        return self._system_template.render().strip()

    def build_review_prompt(
        self,
        *,
        code: str,
        language: str,
        file_name: str | None,
        review_types: list[ReviewCategory],
        severity_threshold: Severity,
    ) -> str:
        return self._review_template.render(
            code=code,
            language=language,
            file_name=file_name,
            review_types=[rt.value for rt in review_types],
            severity_threshold=severity_threshold.value,
        ).strip()

    def build_full_prompt(
        self,
        *,
        code: str,
        language: str,
        file_name: str | None,
        review_types: list[ReviewCategory],
        severity_threshold: Severity,
    ) -> str:
        """Combine system and review prompts for providers that take a single string."""
        system = self.build_system_prompt()
        review = self.build_review_prompt(
            code=code,
            language=language,
            file_name=file_name,
            review_types=review_types,
            severity_threshold=severity_threshold,
        )
        return f"{system}\n\n{review}"
