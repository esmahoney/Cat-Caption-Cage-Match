"""
Health check endpoint.
"""
from fastapi import APIRouter

from ..models import HealthResponse
from .. import __version__

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Check if the API is running."""
    return HealthResponse(status="ok", version=__version__)

