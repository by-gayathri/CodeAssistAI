"""Hugging Face transformer-based review provider (CPU-friendly)."""

from __future__ import annotations

from typing import Any

from app.core.config import Settings, get_settings
from app.core.exceptions import ProviderError
from app.core.logging import get_logger, log_event

logger = get_logger(__name__)


class TransformerProvider:
    """Lazy-load a Hugging Face causal LM and generate review text."""

    name = "transformer"

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._model: Any | None = None
        self._tokenizer: Any | None = None
        self._load_error: str | None = None

    @property
    def model_name(self) -> str:
        return self._settings.transformer_model_name

    def _ensure_loaded(self) -> None:
        if self._model is not None and self._tokenizer is not None:
            return
        if self._load_error is not None:
            raise ProviderError(f"Transformer model unavailable: {self._load_error}")

        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer
        except ImportError as exc:  # pragma: no cover - import environment
            self._load_error = str(exc)
            raise ProviderError(
                "transformers package is required for the transformer provider"
            ) from exc

        try:
            log_event(
                logger,
                "transformer_model_loading",
                model=self.model_name,
                device=self._settings.transformer_device,
            )
            self._tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self._model = AutoModelForCausalLM.from_pretrained(self.model_name)
            device = self._settings.transformer_device
            if device and device != "cpu":
                # Documented CPU default; optional device move without claiming GPU support.
                self._model = self._model.to(device)
            self._model.eval()
            if self._tokenizer.pad_token is None:
                self._tokenizer.pad_token = self._tokenizer.eos_token
            log_event(logger, "transformer_model_loaded", model=self.model_name)
        except Exception as exc:  # noqa: BLE001 - normalize all load failures
            self._load_error = str(exc)
            self._model = None
            self._tokenizer = None
            raise ProviderError(f"Failed to load transformer model: {exc}") from exc

    def generate_review(self, code: str, language: str, prompt: str) -> str:
        """Generate raw model text for the given review prompt."""
        del code, language  # present in prompt; avoid unused-arg warnings
        self._ensure_loaded()
        assert self._model is not None
        assert self._tokenizer is not None

        try:
            import torch

            inputs = self._tokenizer(
                prompt,
                return_tensors="pt",
                truncation=True,
                max_length=2048,
            )
            with torch.no_grad():
                output_ids = self._model.generate(
                    **inputs,
                    max_new_tokens=self._settings.transformer_max_new_tokens,
                    temperature=max(self._settings.transformer_temperature, 1e-5),
                    do_sample=self._settings.transformer_temperature > 0,
                    pad_token_id=self._tokenizer.pad_token_id,
                )
            generated = self._tokenizer.decode(output_ids[0], skip_special_tokens=True)
            # Prefer the continuation after the prompt when present.
            if generated.startswith(prompt):
                generated = generated[len(prompt) :].strip()
            return generated
        except ProviderError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(f"Transformer generation failed: {exc}") from exc
