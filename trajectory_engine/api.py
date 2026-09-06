"""FastAPI read API for the Phase 9 dashboard/GIS contract."""
from __future__ import annotations

import os
import time
from typing import Any, Callable

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from api_contracts import ContractError, alert_resource, error, pagination
from logging_utils import logger, request_id
from trajectory_service import Phase9Service, build_local_demo_service


class ContractResponse(BaseModel):
    contract_version: str = Field(description="Stable dashboard/GIS contract version")


class ErrorResponse(BaseModel):
    contract_version: str
    error: dict[str, Any]


def create_app(service: Phase9Service | None = None,
               runtime_status_provider: Callable[[], dict[str, Any]] | None = None) -> FastAPI:
    owned_directory = None
    if service is None:
        service, owned_directory = build_local_demo_service()
    app = FastAPI(title="SIH26127 Trajectory Intelligence API", version="2.50",
                  description="Read-only API over verified trajectory, analytics, alert, and GIS outputs.")
    cors_origins = [
        origin.strip()
        for origin in os.getenv("TRAJECTORY_CORS_ORIGINS", "").split(",")
        if origin.strip()
    ]
    if cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_credentials=False,
            allow_methods=["GET"],
            allow_headers=["Accept", "Content-Type", "Authorization"],
        )
    app.state.service = service
    app.state.demo_directory = owned_directory
    app.state.runtime_status_provider = runtime_status_provider

    @app.middleware("http")
    async def request_logging(request: Request, call_next):
        rid, started = request_id(), time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            logger.exception("api_request_failed request_id=%s method=%s path=%s", rid, request.method, request.url.path)
            raise
        response.headers["X-Request-ID"] = rid
        logger.info("api_request request_id=%s method=%s path=%s status=%s duration_ms=%.3f", rid, request.method, request.url.path, response.status_code, (time.perf_counter()-started)*1000)
        return response

    @app.exception_handler(ContractError)
    async def contract_error_handler(request: Request, exc: ContractError):
        return JSONResponse(status_code=400, content=error("INVALID_CONTRACT_QUERY", str(exc)))

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(status_code=422, content=error("REQUEST_VALIDATION_ERROR", "Request parameters are invalid", details={"issues": exc.errors()}))

    @app.exception_handler(HTTPException)
    async def http_error_handler(request: Request, exc: HTTPException):
        detail = exc.detail if isinstance(exc.detail, dict) else {"code": "HTTP_ERROR", "message": str(exc.detail)}
        return JSONResponse(status_code=exc.status_code, content={"contract_version": "2.44", "error": detail})

    @app.get("/v1/health")
    def health() -> dict[str, Any]:
        state = app.state.service.snapshot()
        runtime = app.state.runtime_status_provider() if app.state.runtime_status_provider else {
            "mode": "LOCAL_DEMO", "snapshot_ready": True, "last_refresh_succeeded": True,
        }
        return {"contract_version": "2.44", "status": "healthy", "service": "trajectory-intelligence",
                "trajectory_count": len(state.records), "data_mode": runtime["mode"], "runtime": runtime}

    @app.get("/v1/ready")
    def readiness() -> dict[str, Any]:
        app.state.service.snapshot()
        runtime = app.state.runtime_status_provider() if app.state.runtime_status_provider else {
            "mode": "LOCAL_DEMO", "snapshot_ready": True, "last_refresh_succeeded": True,
        }
        return {"contract_version": "2.44", "status": "ready" if runtime["snapshot_ready"] else "not_ready",
                "runtime": runtime}

    @app.get("/v1/trajectories")
    def trajectories(plate: str | None = None, camera: str | None = None, lifecycle_state: str | None = None,
                     usability: str | None = None, offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=1000)) -> dict[str, Any]:
        return {"contract_version": "2.44", **pagination(app.state.service.filter_trajectories(plate=plate, camera=camera, lifecycle_state=lifecycle_state, usability=usability), offset, limit)}

    @app.get("/v1/trajectories/{trajectory_id}")
    def trajectory_detail(trajectory_id: str) -> dict[str, Any]:
        item = app.state.service.trajectory(trajectory_id)
        if item is None:
            raise HTTPException(status_code=404, detail=error("TRAJECTORY_NOT_FOUND", "Trajectory was not found")["error"])
        return {"contract_version": "2.44", "trajectory": item}

    @app.get("/v1/analytics/flows")
    def flows(offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=1000)) -> dict[str, Any]:
        return {"contract_version": "2.44", **pagination(app.state.service.snapshot().flows, offset, limit)}

    @app.get("/v1/analytics/travel-times")
    def travel_times() -> dict[str, Any]:
        return {"contract_version": "2.44", "items": app.state.service.snapshot().travel_times}

    @app.get("/v1/analytics/congestion")
    def congestion() -> dict[str, Any]:
        return {"contract_version": "2.44", "items": app.state.service.snapshot().congestion}

    @app.get("/v1/analytics/origin-destinations")
    def origin_destinations() -> dict[str, Any]:
        return {"contract_version": "2.44", "items": app.state.service.snapshot().routes}

    @app.get("/v1/alerts")
    def alerts(severity: str | None = None, alert_type: str | None = None) -> dict[str, Any]:
        items = app.state.service.snapshot().alerts
        if severity: items = [item for item in items if item["severity"] == severity]
        if alert_type: items = [item for item in items if item.get("alert_type") == alert_type]
        return {"contract_version": "2.44", "items": [alert_resource(item) for item in items]}

    @app.get("/v1/dashboard")
    def dashboard() -> dict[str, Any]:
        return app.state.service.dashboard()

    @app.get("/v1/gis/cameras")
    def gis_cameras() -> dict[str, Any]:
        return app.state.service.dashboard()["gis"]["camera_features"]

    @app.get("/v1/gis/trajectories")
    def gis_trajectories() -> dict[str, Any]:
        return app.state.service.dashboard()["gis"]["trajectory_features"]

    return app


app = create_app()
