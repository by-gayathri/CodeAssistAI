"""In-memory review repository for local development only."""

from __future__ import annotations

from datetime import UTC, datetime
from threading import Lock
from uuid import uuid4

from app.core.exceptions import NotFoundError
from app.models.domain import FeedbackType
from app.models.responses import FeedbackResponse, ReviewResponse


class MemoryReviewRepository:
    """Thread-safe in-memory store. Not durable across process restarts."""

    def __init__(self) -> None:
        self._reviews: dict[str, ReviewResponse] = {}
        self._feedback: dict[str, list[FeedbackResponse]] = {}
        self._lock = Lock()

    def save_review(self, review: ReviewResponse) -> ReviewResponse:
        with self._lock:
            self._reviews[review.review_id] = review
            self._feedback.setdefault(review.review_id, [])
            return review

    def get_review(self, review_id: str) -> ReviewResponse | None:
        with self._lock:
            return self._reviews.get(review_id)

    def save_feedback(
        self,
        *,
        review_id: str,
        finding_id: str | None,
        feedback_type: FeedbackType,
        comment: str | None,
    ) -> FeedbackResponse:
        with self._lock:
            review = self._reviews.get(review_id)
            if review is None:
                raise NotFoundError(f"Review not found: {review_id}")

            if finding_id is not None:
                known = {f.finding_id for f in review.findings}
                if finding_id not in known:
                    raise NotFoundError(f"Finding not found: {finding_id} in review {review_id}")

            item = FeedbackResponse(
                feedback_id=f"feedback-{uuid4().hex[:8]}",
                review_id=review_id,
                finding_id=finding_id,
                feedback_type=feedback_type.value,
                comment=comment,
                created_at=datetime.now(UTC),
            )
            self._feedback.setdefault(review_id, []).append(item)
            return item

    def list_feedback(self, review_id: str) -> list[FeedbackResponse]:
        with self._lock:
            return list(self._feedback.get(review_id, []))

    def clear(self) -> None:
        """Clear all stored data (useful in tests)."""
        with self._lock:
            self._reviews.clear()
            self._feedback.clear()
