"""Origin-Destination (OD) service.

Reconstruct each vehicle's journey from its detections:
  1. group events by plate_number
  2. order that vehicle's detections by event_time
  3. drop exact duplicates
  4. collapse repeated detections at the SAME camera (several frames of one
     car waiting at a camera are NOT a movement)
  5. each consecutive DIFFERENT-camera step is one transition, e.g. 1 -> 2
  6. count every origin->destination transition, including repeated pairs

Safeguards:
  * exact duplicate detections (same plate/camera/time) are removed
  * self-transitions (camera X -> camera X) are never counted
  * repeated transition pairs for the same vehicle are legitimate and retained
"""
from collections import defaultdict

from ..analytics_types import VehicleEvent
from .event_service import dedupe_events


def compute_od_pairs(
    events: list[VehicleEvent],
    camera_names: dict[int, str] | None = None,
) -> tuple[list[dict], int, int]:
    """Return (pairs, total_transitions, vehicles_with_a_journey)."""
    camera_names = camera_names or {}
    events = dedupe_events(events)

    by_plate: dict[str, list[VehicleEvent]] = defaultdict(list)
    for ev in events:
        by_plate[ev.plate_number].append(ev)

    pair_counts: dict[tuple[int, int], int] = defaultdict(int)
    total_transitions = 0
    vehicles_with_journey = 0

    for plate, plate_events in by_plate.items():
        plate_events.sort(key=lambda e: (e.timestamp, e.id or 0))

        # Collapse consecutive same-camera detections into one visit.
        cameras_in_order: list[int] = []
        seen_timestamps: set[object] = set()
        for ev in plate_events:
            if ev.timestamp in seen_timestamps:
                # Two detections at the identical instant for one plate:
                # ordering is ambiguous, skip the later one.
                continue
            seen_timestamps.add(ev.timestamp)
            if not cameras_in_order or cameras_in_order[-1] != ev.camera_id:
                cameras_in_order.append(ev.camera_id)

        if len(cameras_in_order) < 2:
            continue  # seen at only one camera -> no movement to record

        vehicles_with_journey += 1
        # Every consecutive different-camera step is a real movement.
        # Do NOT use a set here: A -> B -> A -> B contains three
        # legitimate transitions, including two separate A -> B movements.
        for origin, dest in zip(cameras_in_order, cameras_in_order[1:]):
            pair_counts[(origin, dest)] += 1
            total_transitions += 1

    pairs = []
    for (origin, dest), count in pair_counts.items():
        pairs.append(
            {
                "origin_camera": origin,
                "origin_camera_name": camera_names.get(origin, f"CAM{origin}"),
                "destination_camera": dest,
                "destination_camera_name": camera_names.get(dest, f"CAM{dest}"),
                "vehicle_count": count,
            }
        )
    # Busiest route first; stable tie-break by camera ids.
    pairs.sort(
        key=lambda p: (-p["vehicle_count"], p["origin_camera"], p["destination_camera"])
    )
    return pairs, total_transitions, vehicles_with_journey
