"""Review and feedback repository protocol."""

from __future__ import annotations

from typing import Protocol

from app.models.domain import FeedbackType
from app.models.responses import FeedbackResponse, ReviewResponse


class ReviewRepository(Protocol):
    def save_review(self, review: ReviewResponse) -> ReviewResponse: ...

    def get_review(self, review_id: str) -> ReviewResponse | None: ...

    def save_feedback(
        self,
        *,
        review_id: str,
        finding_id: str | None,
        feedback_type: FeedbackType,
        comment: str | None,
    ) -> FeedbackResponse: ...

    def list_feedback(self, review_id: str) -> list[FeedbackResponse]: ...
