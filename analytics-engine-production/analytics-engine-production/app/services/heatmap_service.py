"""Heatmap service.

Produces one point per camera with coordinates (from the PostGIS location),
the distinct vehicle count for the window, and a traffic level - ready for a
frontend GIS/map library (e.g. Leaflet, Mapbox, OpenLayers).

Only KNOWN cameras (present in the cameras table, with coordinates) are
mapped. A camera id that appears in plate_events but has no cameras row is
"unknown" and is returned separately so the API can flag it.
"""
from ..analytics_types import CameraInfo
from .density_service import traffic_level
from .event_service import distinct_vehicles_by_camera


def build_heatmap(
    events,
    cameras: dict[int, CameraInfo],
) -> tuple[list[dict], list[int]]:
    """Return (points, unknown_camera_ids)."""
    distinct = distinct_vehicles_by_camera(events)

    points: list[dict] = []
    for cam_id, cam in sorted(cameras.items()):
        count = distinct.get(cam_id, 0)
        points.append(
            {
                "camera_id": cam_id,
                "camera_name": cam.name,
                "latitude": cam.latitude,
                "longitude": cam.longitude,
                "vehicle_count": count,
                "traffic_level": traffic_level(count),
            }
        )

    unknown = sorted(cid for cid in distinct if cid not in cameras)
    return points, unknown
