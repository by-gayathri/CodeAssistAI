"""Thin service wrapper used by higher-level tooling if needed."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from evaluation.run_evaluation import run_evaluation


class EvaluationService:
    """Facade over the evaluation runner for programmatic use."""

    def run(
        self,
        *,
        dataset_path: Path | None = None,
        output_path: Path | None = None,
        provider_name: str = "mock",
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {"provider_name": provider_name}
        if dataset_path is not None:
            kwargs["dataset_path"] = dataset_path
        if output_path is not None:
            kwargs["output_path"] = output_path
        return run_evaluation(**kwargs)
