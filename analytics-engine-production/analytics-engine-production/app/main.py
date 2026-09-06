"""FastAPI application entry point.

Run with:  uvicorn app.main:app --reload
Interactive docs:  http://127.0.0.1:8000/docs
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .database import init_db
from .routes import analytics, health


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables the engine needs on startup (safe; see database.init_db).
    init_db()
    settings = get_settings()
    if not settings.analytics_api_key:
        print(
            "\n[WARNING] ANALYTICS_API_KEY is not set - running in DEVELOPMENT "
            "MODE (API-key auth disabled). Do NOT run like this in production.\n"
        )
    yield


app = FastAPI(
    title="ANPR Traffic Analytics Engine",
    version="1.0.0",
    description=(
        "Analytics over ANPR plate-detection events: time windows, traffic "
        "density, origin-destination, heatmap, congestion and trends. "
        "Reads the existing `plate_events` and `cameras` (PostGIS) tables."
    ),
    lifespan=lifespan,
)

_settings = get_settings()
if _settings.cors_origins.strip():
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[origin.strip() for origin in _settings.cors_origins.split(",") if origin.strip()],
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["X-API-Key", "Content-Type"],
    )

app.include_router(health.router)
app.include_router(analytics.router)


@app.get("/", include_in_schema=False)
def root() -> dict:
    return {
        "service": "ANPR Traffic Analytics Engine",
        "docs": "/docs",
        "health": "/health",
    }
