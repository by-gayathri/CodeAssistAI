"""Code review API routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.deps import get_review_service
from app.core.exceptions import NotFoundError
from app.models.requests import FeedbackRequest, ReviewRequest
from app.models.responses import FeedbackResponse, ReviewResponse
from app.services.review_service import ReviewService

router = APIRouter(prefix="/api/v1/reviews", tags=["reviews"])

ReviewServiceDep = Annotated[ReviewService, Depends(get_review_service)]


@router.post(
    "",
    response_model=ReviewResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a code review",
    description=(
        "Accepts source code and review configuration, then returns structured findings. "
        "Submitted code is never executed."
    ),
    responses={
        400: {"description": "Business validation error"},
        422: {"description": "Request validation error"},
        502: {"description": "Provider or parse failure"},
    },
)
def create_review(body: ReviewRequest, service: ReviewServiceDep) -> ReviewResponse:
    return service.create_review(body)


@router.get(
    "/{review_id}",
    response_model=ReviewResponse,
    summary="Get a previous review",
    description=(
        "Returns a previously generated review from the in-memory repository "
        "(development only; not durable)."
    ),
    responses={404: {"description": "Review not found"}},
)
def get_review(review_id: str, service: ReviewServiceDep) -> ReviewResponse:
    review = service.get_review(review_id)
    if review is None:
        raise NotFoundError(f"Review not found: {review_id}")
    return review


@router.post(
    "/{review_id}/feedback",
    response_model=FeedbackResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit review feedback",
    description="Store feedback about a finding or an entire review.",
    responses={404: {"description": "Review or finding not found"}},
)
def submit_feedback(
    review_id: str,
    body: FeedbackRequest,
    service: ReviewServiceDep,
) -> FeedbackResponse:
    return service.add_feedback(review_id, body)
