"""Health check endpoint (no API key required)."""
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
def health(db: Session = Depends(get_db)) -> dict:
    """Confirm the service is up and can reach the database."""
    settings = get_settings()
    db_status = "connected"
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_status = "error"

    return {
        "status": "ok" if db_status == "connected" else "degraded",
        "database": db_status,
        "database_backend": (
            "postgresql+postgis" if not settings.is_sqlite else "sqlite-mirror"
        ),
        "auth_enabled": bool(settings.analytics_api_key),
    }
