"""Application-specific exceptions and error payloads."""

from __future__ import annotations

from typing import Any


class CodeAssistAIError(Exception):
    """Base application error."""

    def __init__(self, message: str, *, code: str = "internal_error") -> None:
        super().__init__(message)
        self.message = message
        self.code = code

    def to_dict(self) -> dict[str, Any]:
        return {"error": {"code": self.code, "message": self.message}}


class ValidationAppError(CodeAssistAIError):
    """Raised when business validation fails outside Pydantic."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="validation_error")


class ProviderError(CodeAssistAIError):
    """Raised when a model provider fails."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="provider_error")


class ParseError(CodeAssistAIError):
    """Raised when model output cannot be parsed into the review schema."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="parse_error")


class NotFoundError(CodeAssistAIError):
    """Raised when a review or finding cannot be found."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="not_found")
