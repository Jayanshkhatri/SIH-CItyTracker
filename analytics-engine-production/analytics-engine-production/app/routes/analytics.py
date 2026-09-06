"""Analytics endpoints.

Every endpoint accepts the same optional time-window parameters:
    window = 15m | 30m | 1h | 3h        (default 1h)
    start  = ISO-8601 timestamp         (custom range, use together)
    end    = ISO-8601 timestamp         (custom range, use together)

All analytics endpoints require the  X-API-Key  header when
ANALYTICS_API_KEY is configured.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_db
from .. import repository
from ..security import require_api_key
from ..time_utils import resolve_time_window
from ..services import (
    congestion_service,
    density_service,
    event_service,
    heatmap_service,
    od_service,
    trend_service,
)

router = APIRouter(
    prefix="/analytics",
    tags=["analytics"],
    dependencies=[Depends(require_api_key)],
)

DENSITY_DEFINITION = (
    "Vehicle count (distinct plate_number) per camera for the selected time "
    "window. This is NOT physical density (vehicles/km); road-length/capacity "
    "data is not available."
)


def _camera_name_map(cameras: dict) -> dict[int, str]:
    return {cid: cam.name for cid, cam in cameras.items()}


@router.get("/events")
def get_events(
    window: str | None = Query(None, description="Named window: 15m, 30m, 1h, 3h"),
    start: str | None = Query(None, description="ISO-8601 start (with end)"),
    end: str | None = Query(None, description="ISO-8601 end (with start)"),
    db: Session = Depends(get_db),
) -> dict:
    """Raw ANPR plate events within the time window."""
    start_dt, end_dt, label = resolve_time_window(window, start, end)
    events = repository.get_events(db, start_dt, end_dt)
    cameras = repository.get_cameras(db)
    deduped = event_service.dedupe_events(events)

    return {
        "start": start_dt,
        "end": end_dt,
        "window_label": label,
        "total_events": len(deduped),
        "unique_vehicles": event_service.unique_plate_count(deduped),
        "events": [
            {
                "id": ev.id,
                "plate_number": ev.plate_number,
                "camera_id": ev.camera_id,
                "camera_name": cameras[ev.camera_id].name if ev.camera_id in cameras else None,
                "event_time": ev.timestamp,
                "confidence": ev.confidence,
            }
            for ev in deduped
        ],
    }


@router.get("/density")
def get_density(
    window: str | None = Query(None),
    start: str | None = Query(None),
    end: str | None = Query(None),
    db: Session = Depends(get_db),
) -> dict:
    """Distinct vehicle count and traffic level per camera."""
    s = get_settings()
    start_dt, end_dt, label = resolve_time_window(window, start, end)
    events = repository.get_events(db, start_dt, end_dt)
    cameras = repository.get_cameras(db)
    events = event_service.dedupe_events(events)

    distinct = event_service.distinct_vehicles_by_camera(events)
    rows = density_service.build_density(distinct, _camera_name_map(cameras))

    return {
        "start": start_dt,
        "end": end_dt,
        "window_label": label,
        "definition": DENSITY_DEFINITION,
        "thresholds": {
            "low": s.density_low_threshold,
            "high": s.density_high_threshold,
        },
        "total_vehicles": sum(distinct.values()),
        "camera_count": len(rows),
        "cameras": rows,
    }


@router.get("/od")
def get_od(
    window: str | None = Query(None),
    start: str | None = Query(None),
    end: str | None = Query(None),
    db: Session = Depends(get_db),
) -> dict:
    """Origin->destination transition counts between cameras."""
    start_dt, end_dt, label = resolve_time_window(window, start, end)
    events = repository.get_events(db, start_dt, end_dt)
    cameras = repository.get_cameras(db)

    pairs, total_transitions, vehicles = od_service.compute_od_pairs(
        events, _camera_name_map(cameras)
    )

    return {
        "start": start_dt,
        "end": end_dt,
        "window_label": label,
        "total_transitions": total_transitions,
        "vehicles_with_journey": vehicles,
        "note": (
            "Each vehicle's detections are ordered by event_time; consecutive "
            "different cameras form one transition. Repeated detections at the "
            "same camera and exact duplicates are collapsed."
        ),
        "pairs": pairs,
    }


@router.get("/heatmap")
def get_heatmap(
    window: str | None = Query(None),
    start: str | None = Query(None),
    end: str | None = Query(None),
    db: Session = Depends(get_db),
) -> dict:
    """Per-camera coordinates + vehicle count, for a frontend map."""
    start_dt, end_dt, label = resolve_time_window(window, start, end)
    events = repository.get_events(db, start_dt, end_dt)
    cameras = repository.get_cameras(db)
    events = event_service.dedupe_events(events)

    points, unknown = heatmap_service.build_heatmap(events, cameras)

    return {
        "start": start_dt,
        "end": end_dt,
        "window_label": label,
        "points": points,
        "unknown_camera_ids": unknown,
    }


@router.get("/congestion")
def get_congestion(
    window: str | None = Query(None),
    start: str | None = Query(None),
    end: str | None = Query(None),
    period: str = Query("1h", description="Baseline period label: 15m,30m,1h,3h"),
    db: Session = Depends(get_db),
) -> dict:
    """Compare current camera counts against baselines."""
    s = get_settings()
    start_dt, end_dt, label = resolve_time_window(window, start, end)
    events = repository.get_events(db, start_dt, end_dt)
    cameras = repository.get_cameras(db)
    events = event_service.dedupe_events(events)

    period_minutes = {"15m": 15, "30m": 30, "1h": 60, "3h": 180}.get(period, 60)

    baselines: dict[int, float] = {}
    source = "traffic_baselines"
    used_fallback = False
    for cam_id in cameras:
        base = repository.get_baseline(db, cam_id, period)
        if base is None:
            # Fallback: derive a baseline from recent history if available.
            base = repository.historical_average(
                db, cam_id, end_dt, period_minutes=period_minutes
            )
            if base is not None:
                used_fallback = True
        if base is not None:
            baselines[cam_id] = float(base)

    if used_fallback and not baselines:
        source = "historical_fallback"
    elif used_fallback:
        source = "traffic_baselines+historical_fallback"
    elif not baselines:
        source = "none"

    points = congestion_service.evaluate_congestion(events, cameras, baselines)

    return {
        "start": start_dt,
        "end": end_dt,
        "window_label": label,
        "threshold_ratio": s.congestion_threshold,
        "period": period,
        "baseline_source": source,
        "points": points,
    }


@router.get("/trends")
def get_trends(
    window: str | None = Query(None),
    start: str | None = Query(None),
    end: str | None = Query(None),
    bucket_minutes: int | None = Query(None, description="Bucket size in minutes"),
    per_camera: bool = Query(False, description="Include per-camera counts"),
    db: Session = Depends(get_db),
) -> dict:
    """Time-bucketed counts for trend graphs."""
    s = get_settings()
    start_dt, end_dt, label = resolve_time_window(window, start, end)
    events = repository.get_events(db, start_dt, end_dt)
    events = event_service.dedupe_events(events)

    bucket = bucket_minutes or s.default_bucket_minutes
    buckets = trend_service.build_trends(
        events, start_dt, end_dt, bucket, include_per_camera=per_camera
    )

    return {
        "start": start_dt,
        "end": end_dt,
        "window_label": label,
        "bucket_minutes": bucket,
        "bucket_count": len(buckets),
        "buckets": buckets,
    }
