"""
CEREVIORA — Health Check Endpoint

GET /health is always the first endpoint to implement.
Monitoring tools, CI pipelines and load balancers use it to verify
that the service started correctly and can reach its dependencies.
"""
from fastapi import APIRouter
from pydantic import BaseModel
from datetime import datetime, timezone
from app.config import settings

router = APIRouter()


class HealthResponse(BaseModel):
    """Typed response model so FastAPI generates accurate OpenAPI docs."""
    status: str
    app: str
    version: str
    timestamp: str


@router.get("/health", response_model=HealthResponse, tags=["System"])
def health_check():
    """
    Returns 200 OK with basic application metadata.

    This endpoint intentionally has no database dependency so it
    succeeds even when the database is temporarily unavailable.
    """
    return HealthResponse(
        status="ok",
        app=settings.app_name,
        version=settings.app_version,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
