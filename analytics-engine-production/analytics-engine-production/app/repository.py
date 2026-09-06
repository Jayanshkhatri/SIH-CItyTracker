"""Data access layer (the ONLY module that writes SQL).

All analytics services call functions here. When you connect the real
ANPR database, this is the only place you adjust - the algorithms in
app/services never change.

Coordinates:
  Production (PostgreSQL + PostGIS): lat/lng are read from
      cameras.location  (GEOGRAPHY(POINT))
  using:
      ST_Y(location::geometry)  -> latitude
      ST_X(location::geometry)  -> longitude
  Local development (SQLite): the seed stores 'lng lat' in `location`,
  and we parse it in Python here, so the same code runs everywhere.

Timestamps:
  `plate_events.event_time` is treated as UTC. We store/compare naive UTC
  at the database boundary and convert to aware-UTC on the way out.
"""
from datetime import datetime, timezone

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from .analytics_types import CameraInfo, VehicleEvent
from .config import get_settings
from .models import Camera, PlateEvent, TrafficBaseline

settings = get_settings()


def _to_naive_utc(dt: datetime) -> datetime:
    """Convert an aware UTC datetime to naive UTC for the DB column."""
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _to_aware_utc(dt: datetime | None) -> datetime | None:
    """Convert a naive DB timestamp to timezone-aware UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _parse_location(loc: str | None) -> tuple[float | None, float | None]:
    """Parse a SQLite-mirror location string 'lng lat' (or 'lng,lat').

    On PostGIS this branch is not used (coordinates come from ST_X/ST_Y).
    """
    if not loc:
        return None, None
    try:
        parts = loc.replace(",", " ").split()
        lng, lat = float(parts[0]), float(parts[1])
        return lat, lng
    except (ValueError, IndexError):
        return None, None


def get_cameras(db: Session) -> dict[int, CameraInfo]:
    """Return all cameras as {camera_id: CameraInfo}.

    Uses PostGIS ST_X/ST_Y on PostgreSQL; parses the text location on
    SQLite. Either way the app receives clean latitude/longitude numbers.
    """
    if settings.is_sqlite:
        rows = db.execute(select(Camera.id, Camera.name, Camera.location)).all()
        result: dict[int, CameraInfo] = {}
        for cid, name, loc in rows:
            lat, lng = _parse_location(loc)
            result[cid] = CameraInfo(camera_id=cid, name=name or f"CAM{cid}",
                                     latitude=lat, longitude=lng)
        return result

    # PostgreSQL + PostGIS: extract coordinates with PostGIS functions.
    sql = text(
        """
        SELECT id,
               name,
               ST_Y(location::geometry) AS lat,
               ST_X(location::geometry) AS lng
        FROM cameras
        """
    )
    result = {}
    for cid, name, lat, lng in db.execute(sql).all():
        result[cid] = CameraInfo(
            camera_id=cid, name=name or f"CAM{cid}", latitude=lat, longitude=lng
        )
    return result


def get_events(
    db: Session, start: datetime, end: datetime
) -> list[VehicleEvent]:
    """Return detections with start <= event_time < end (half-open window).

    Ordered by (event_time, id) so analytics output is deterministic.
    Timestamps are validated/converted to aware-UTC.
    """
    start = _to_naive_utc(start)
    end = _to_naive_utc(end)
    if settings.is_sqlite:
        stmt = (
            select(PlateEvent)
            .where(
                func.datetime(PlateEvent.event_time) >= func.datetime(start),
                func.datetime(PlateEvent.event_time) < func.datetime(end),
            )
            .order_by(PlateEvent.event_time, PlateEvent.id)
        )
    else:
        stmt = (
            select(PlateEvent)
            .where(PlateEvent.event_time >= start, PlateEvent.event_time < end)
            .order_by(PlateEvent.event_time, PlateEvent.id)
        )
    rows = db.execute(stmt).scalars().all()
    return [
        VehicleEvent(
            id=r.id,
            plate_number=r.plate_number or "",
            camera_id=r.camera_id,
            timestamp=_to_aware_utc(r.event_time),  # type: ignore[arg-type]
            confidence=r.confidence,
        )
        for r in rows
    ]


def get_baseline(db: Session, camera_id: int, period: str) -> float | None:
    """Return the mock/stored baseline average for a camera+period, if any."""
    stmt = select(TrafficBaseline.average_vehicle_count).where(
        TrafficBaseline.camera_id == camera_id,
        TrafficBaseline.time_period == period,
    )
    return db.execute(stmt).scalar_one_or_none()


def historical_average(
    db: Session,
    camera_id: int,
    end: datetime,
    period_minutes: int = 60,
    days: int = 7,
) -> float | None:
    """Fallback baseline: average distinct vehicles seen per comparable
    window over the past `days` days of real history.

    Used only when no row exists in traffic_baselines. We bucket history
    into windows of the same length as the requested one and average the
    per-window distinct-plate counts. Returns None if there is no history.

    The CURRENT window (the period being evaluated) is EXCLUDED - otherwise
    a spike would inflate its own baseline. We look at the `days` before the
    current window started.
    """
    from datetime import timedelta

    period = timedelta(minutes=period_minutes)
    # History ends right when the current window begins.
    history_end = end - period
    history_start = history_end - timedelta(days=days)
    start_naive = _to_naive_utc(history_start)
    end_naive = _to_naive_utc(history_end)
    stmt = select(PlateEvent.event_time, PlateEvent.plate_number).where(
        PlateEvent.camera_id == camera_id,
        PlateEvent.event_time >= start_naive,
        PlateEvent.event_time < end_naive,
    )
    rows = db.execute(stmt).all()
    if not rows:
        return None

    bucket_seconds = period_minutes * 60
    end_epoch = end_naive.timestamp()
    buckets: dict[int, set[str]] = {}
    for event_time, plate in rows:
        ts = event_time.timestamp()
        if event_time.tzinfo is None:
            ts = event_time.replace(tzinfo=timezone.utc).timestamp()
        b = int((end_epoch - ts) // bucket_seconds)
        buckets.setdefault(b, set()).add(plate or "")
    if not buckets:
        return None
    return sum(len(v) for v in buckets.values()) / len(buckets)
