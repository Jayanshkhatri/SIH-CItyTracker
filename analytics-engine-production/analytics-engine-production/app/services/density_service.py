"""Density service.

MVP DEFINITION (important):
  "traffic density" = number of vehicles (distinct plates) detected per
  camera during the selected time window.
  It is NOT physical density (vehicles per km) - that would require road
  length / lane capacity data we do not have.
"""
from ..config import get_settings


def traffic_level(vehicle_count: int) -> str:
    """Classify a vehicle count into LOW / MEDIUM / HIGH."""
    s = get_settings()
    if vehicle_count < s.density_low_threshold:
        return "LOW"
    if vehicle_count < s.density_high_threshold:
        return "MEDIUM"
    return "HIGH"


def build_density(
    distinct_by_camera: dict[int, int],
    camera_names: dict[int, str] | None = None,
) -> list[dict]:
    """Turn {camera_id: distinct_vehicle_count} into a sorted list.

    Sorted by vehicle_count descending (busiest first), then camera_id.
    """
    camera_names = camera_names or {}
    rows = [
        {
            "camera_id": cam,
            "camera_name": camera_names.get(cam, f"CAM{cam}"),
            "vehicle_count": cnt,
            "traffic_level": traffic_level(cnt),
        }
        for cam, cnt in distinct_by_camera.items()
    ]
    rows.sort(key=lambda r: (-r["vehicle_count"], r["camera_id"]))
    return rows
