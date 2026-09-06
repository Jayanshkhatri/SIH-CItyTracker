"""Event service - de-duplication and counting helpers.

These functions take the standard VehicleEvent objects (see
app/analytics_types.py), NOT database rows. That keeps the analytics logic
independent of where the data comes from.
"""
from collections import defaultdict

from ..analytics_types import VehicleEvent


def dedupe_events(events: list[VehicleEvent]) -> list[VehicleEvent]:
    """Remove exact duplicate detections.

    A duplicate = same (plate_number, camera_id, timestamp). Real ANPR feeds
    can emit the same detection twice; we keep the first occurrence.
    """
    seen: set[tuple[str, int, object]] = set()
    result: list[VehicleEvent] = []
    for ev in events:
        key = (ev.plate_number, ev.camera_id, ev.timestamp)
        if key in seen:
            continue
        seen.add(key)
        result.append(ev)
    return result


def count_events_by_camera(events: list[VehicleEvent]) -> dict[int, int]:
    """Count raw detections per camera_id (every frame/detection counts)."""
    counts: dict[int, int] = defaultdict(int)
    for ev in events:
        counts[ev.camera_id] += 1
    return dict(counts)


def distinct_vehicles_by_camera(events: list[VehicleEvent]) -> dict[int, int]:
    """Count DISTINCT plate_number per camera.

    Because the same vehicle may be detected several times at one camera,
    this is the "number of vehicles" measure used for density/heatmap/
    congestion (per the product requirement).
    """
    plates: dict[int, set[str]] = defaultdict(set)
    for ev in events:
        plates[ev.camera_id].add(ev.plate_number)
    return {cam: len(p) for cam, p in plates.items()}


def unique_plate_count(events: list[VehicleEvent]) -> int:
    return len({ev.plate_number for ev in events})
