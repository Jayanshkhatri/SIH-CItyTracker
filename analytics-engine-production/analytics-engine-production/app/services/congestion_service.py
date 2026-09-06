"""Congestion service.

For every camera we compare the current distinct-vehicle count against a
baseline ("normal") count:

    ratio           = current_count / baseline_count
    percent_increase = (current_count - baseline_count) / baseline_count * 100

A camera is CONGESTED when ratio >= CONGESTION_THRESHOLD (configurable via
env var, default 1.5 = "50% busier than normal").

Status values:
    NORMAL        - current at/under the congestion threshold
    CONGESTED     - current at/over the threshold
    NO_BASELINE   - no baseline and no usable history -> cannot judge

The baseline is looked up by the route/repository (mock traffic_baselines
table, or a computed historical fallback). This service only does the math,
so it stays deterministic and easy to test.
"""
from ..analytics_types import CameraInfo
from ..config import get_settings
from .event_service import distinct_vehicles_by_camera


def evaluate_congestion(
    events,
    cameras: dict[int, CameraInfo],
    baselines: dict[int, float],
) -> list[dict]:
    """Build congestion results for every known camera.

    `baselines` maps camera_id -> baseline count (may be missing/None).
    """
    s = get_settings()
    distinct = distinct_vehicles_by_camera(events)

    points: list[dict] = []
    for cam_id in sorted(cameras):
        current = distinct.get(cam_id, 0)
        baseline = baselines.get(cam_id)

        if baseline is None or baseline <= 0:
            status = "NO_BASELINE"
            ratio = 0.0
            percent: float | None = None
            baseline_out = 0.0
        else:
            ratio = round(current / baseline, 3)
            percent = round((current - baseline) / baseline * 100, 1)
            status = "CONGESTED" if ratio >= s.congestion_threshold else "NORMAL"
            baseline_out = round(float(baseline), 1)

        points.append(
            {
                "camera_id": cam_id,
                "camera_name": cameras[cam_id].name,
                "current_count": current,
                "baseline_count": baseline_out,
                "ratio": ratio,
                "percent_increase": percent,
                "congestion_status": status,
            }
        )
    return points
