"""Health check route."""

from fastapi import APIRouter

from app import __version__
from app.core.config import get_settings
from app.models.responses import HealthResponse

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Service health",
    description="Returns service health information.",
)
def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="healthy",
        service=settings.app_name,
        version=settings.app_version or __version__,
    )
