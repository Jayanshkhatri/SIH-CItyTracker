"""Trend service.

Splits the selected period into fixed time buckets (default 15 minutes) and,
for each bucket, counts:
  * total_events     - raw detections
  * unique_vehicles  - distinct plate_numbers
  * per_camera       - distinct vehicles per camera (optional, for stacked
                       charts)

Half-open buckets: [bucket_start, bucket_end). Buckets are aligned to the
window start so results line up with the requested time range.
"""
from datetime import datetime, timedelta, timezone
from math import ceil

from ..analytics_types import VehicleEvent


def build_trends(
    events: list[VehicleEvent],
    start: datetime,
    end: datetime,
    bucket_minutes: int,
    include_per_camera: bool = False,
) -> list[dict]:
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    start = start.astimezone(timezone.utc)
    end = end.astimezone(timezone.utc)

    bucket = timedelta(minutes=bucket_minutes)
    total_seconds = (end - start).total_seconds()
    bucket_count = max(1, ceil(total_seconds / bucket.total_seconds()))

    # Initialise every bucket (even empty ones) so charts have a full axis.
    buckets: list[dict] = []
    for i in range(bucket_count):
        b_start = start + i * bucket
        b_end = min(b_start + bucket, end)
        buckets.append(
            {
                "bucket_start": b_start,
                "bucket_end": b_end,
                "total_events": 0,
                "_plates": set(),
                "_per_camera": {},
            }
        )

    for ev in events:
        ts = ev.timestamp.astimezone(timezone.utc)
        idx = int((ts - start).total_seconds() // bucket.total_seconds())
        if idx < 0 or idx >= bucket_count:
            continue  # outside the window (shouldn't happen, safe guard)
        b = buckets[idx]
        b["total_events"] += 1
        b["_plates"].add(ev.plate_number)
        cam = b["_per_camera"].setdefault(ev.camera_id, set())
        cam.add(ev.plate_number)

    result: list[dict] = []
    for b in buckets:
        row = {
            "bucket_start": b["bucket_start"],
            "bucket_end": b["bucket_end"],
            "total_events": b["total_events"],
            "unique_vehicles": len(b["_plates"]),
        }
        if include_per_camera:
            row["per_camera"] = {
                str(cam): len(plates) for cam, plates in sorted(b["_per_camera"].items())
            }
        result.append(row)
    return result
