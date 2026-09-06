"""Unit tests for the OD algorithm's duplicate/movement safeguards."""
from datetime import datetime, timedelta, timezone

from app.analytics_types import VehicleEvent
from app.services.od_service import compute_od_pairs


def _ev(plate, cam, minutes_ago, eid=None):
    return VehicleEvent(
        plate_number=plate,
        camera_id=cam,
        timestamp=datetime.now(timezone.utc) - timedelta(minutes=minutes_ago),
        confidence=0.95,
        id=eid,
    )


def test_exact_duplicates_ignored():
    # Two identical detections (same plate/camera/time) must count once.
    t = datetime.now(timezone.utc)
    e1 = VehicleEvent("P1", 1, t, id=1)
    e2 = VehicleEvent("P1", 1, t, id=2)  # exact duplicate
    e3 = VehicleEvent("P1", 2, t + timedelta(minutes=5), id=3)
    pairs, total, vehicles = compute_od_pairs([e1, e2, e3])
    assert total == 1
    assert pairs[0]["origin_camera"] == 1
    assert pairs[0]["destination_camera"] == 2
    assert pairs[0]["vehicle_count"] == 1
    assert vehicles == 1


def test_repeated_same_camera_not_a_transition():
    # Car seen 3 times at camera 2 then camera 3: only 2->3 counts.
    events = [
        _ev("P1", 2, 30, 1),
        _ev("P1", 2, 20, 2),
        _ev("P1", 2, 10, 3),
        _ev("P1", 3, 5, 4),
    ]
    pairs, total, _ = compute_od_pairs(events)
    assert total == 1
    assert (pairs[0]["origin_camera"], pairs[0]["destination_camera"]) == (2, 3)


def test_multiple_vehicles_same_route_counted():
    events = []
    for i in range(4):
        events.append(_ev(f"P{i}", 1, 20 + i, i))
        events.append(_ev(f"P{i}", 2, 10 + i, i + 100))
    pairs, total, vehicles = compute_od_pairs(events)
    assert total == 4
    assert vehicles == 4
    assert pairs[0]["vehicle_count"] == 4


def test_single_camera_vehicle_has_no_journey():
    events = [_ev("P9", 5, 10, 1), _ev("P9", 5, 5, 2)]
    pairs, total, vehicles = compute_od_pairs(events)
    assert pairs == []
    assert total == 0
    assert vehicles == 0


def test_empty_dataset():
    pairs, total, vehicles = compute_od_pairs([])
    assert pairs == [] and total == 0 and vehicles == 0
