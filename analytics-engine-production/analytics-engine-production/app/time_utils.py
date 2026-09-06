"""Time-window helpers.

Rules used everywhere in the engine:
* Timestamps are handled in UTC.
* A time window is HALF-OPEN: [start, end) -> start inclusive, end exclusive.
* Naive timestamps (no timezone) are assumed to be UTC.
"""
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException

# Named windows the API understands. Values are minutes; None = custom.
NAMED_WINDOWS: dict[str, timedelta] = {
    "15m": timedelta(minutes=15),
    "30m": timedelta(minutes=30),
    "1h": timedelta(hours=1),
    "3h": timedelta(hours=3),
}

# Friendly aliases users may type instead of "15m".
WINDOW_ALIASES: dict[str, str] = {
    "last_15_minutes": "15m",
    "last_30_minutes": "30m",
    "last_1_hour": "1h",
    "last_3_hours": "3h",
    "15minutes": "15m",
    "30minutes": "30m",
    "1hour": "1h",
    "3hours": "3h",
}


def ensure_utc(dt: datetime) -> datetime:
    """Return dt as a timezone-aware datetime in UTC.

    Naive datetimes are assumed to already be UTC (the engine stores UTC).
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def parse_iso8601(value: str, field_name: str) -> datetime:
    """Parse an ISO-8601 timestamp (e.g. 2026-09-04T10:00:00Z)."""
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid timestamp for '{field_name}': {value!r}. "
                "Use ISO-8601 format, e.g. 2026-09-04T10:00:00Z"
            ),
        )
    return ensure_utc(dt)


def resolve_time_window(
    window: str | None,
    start: str | None,
    end: str | None,
) -> tuple[datetime, datetime, str]:
    """Resolve query parameters into (start, end, label) in UTC.

    Priority:
      1. Custom range: both start and end provided.
      2. Named window:  window=15m|30m|1h|3h  (default 1h).
    """
    now = datetime.now(timezone.utc)

    if start or end:
        # Custom range - both values are required.
        if not start or not end:
            raise HTTPException(
                status_code=400,
                detail="Custom time range requires BOTH 'start' and 'end' "
                "ISO-8601 timestamps.",
            )
        start_dt = parse_iso8601(start, "start")
        end_dt = parse_iso8601(end, "end")
        if end_dt <= start_dt:
            raise HTTPException(
                status_code=400,
                detail="'end' must be later than 'start'.",
            )
        return start_dt, end_dt, "custom"

    label = (window or "1h").strip().lower()
    label = WINDOW_ALIASES.get(label, label)

    if label not in NAMED_WINDOWS:
        allowed = ", ".join(sorted(NAMED_WINDOWS))
        raise HTTPException(
            status_code=400,
            detail=f"Unknown window {window!r}. Allowed values: {allowed}.",
        )

    delta = NAMED_WINDOWS[label]
    return now - delta, now, label
