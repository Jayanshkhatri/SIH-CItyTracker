"""
analytics.py
Everything that happens AFTER a plate is detected and saved:
  - build the full multi-camera trajectory for a vehicle
  - flag speeding between two consecutive cameras
  - flag blacklisted plates
  - flag "route anomalies" (seen at an earlier camera, never showed up at a
    later camera that has already been processed)
"""

import json
import os
from . import db
from .geo import compute_leg

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "cameras.json")


def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)


def get_trajectory(plate):
    """Full ordered path + per-leg distance/time/speed for one plate."""
    dets = db.get_vehicle_detections(plate)
    legs = []
    for i in range(len(dets) - 1):
        legs.append(compute_leg(dets[i], dets[i + 1]))
    return {"plate": plate, "detections": dets, "legs": legs}


def check_blacklist(plate):
    hit = db.is_blacklisted(plate)
    if hit:
        msg = f"Blacklisted vehicle detected ({hit.get('reason', 'no reason given')})"
        if not db.alert_exists(plate, "blacklist", msg):
            db.insert_alert(plate, "blacklist", msg)


def check_speeding(plate):
    config = load_config()
    limit = config.get("speed_limit_kmh", 80)
    traj = get_trajectory(plate)
    for leg in traj["legs"]:
        if leg["speed_kmh"] > limit:
            msg = (
                f"{leg['from_camera']} -> {leg['to_camera']}: "
                f"{leg['speed_kmh']} km/h (limit {limit} km/h)"
            )
            if not db.alert_exists(plate, "speeding", msg):
                db.insert_alert(plate, "speeding", msg)


def check_route_anomalies():
    """
    Route logic: cameras.json defines an expected `route_order`, e.g.
    CAM_A -> CAM_B -> CAM_C. If a plate was seen at CAM_A, and CAM_B has
    ALREADY been processed (i.e. we have data for it), but the plate never
    shows up at CAM_B, that is a Route Anomaly - the vehicle disappeared
    from the expected corridor.

    We only flag a gap once "enough time" has passed (max_travel_hours),
    so we don't flag vehicles that just haven't reached the next camera yet.
    """
    import time
    config = load_config()
    route_order = config.get("route_order", [])
    max_hours = config.get("max_travel_hours_before_anomaly", 3)
    processed = set(db.get_processed_cameras())

    plates = db.get_distinct_plates()
    for plate in plates:
        dets = db.get_vehicle_detections(plate)
        seen_cameras = {d["camera_id"]: d for d in dets}

        for i, cam_id in enumerate(route_order):
            if cam_id not in seen_cameras:
                continue
            seen_time = seen_cameras[cam_id]["timestamp"]
            hours_elapsed = (time.time() - seen_time) / 3600.0
            if hours_elapsed < max_hours:
                continue  # too soon to call it an anomaly

            # look at every later camera in the route that has already been processed
            for later_cam in route_order[i + 1:]:
                if later_cam in processed and later_cam not in seen_cameras:
                    msg = (
                        f"Seen at {seen_cameras[cam_id]['camera_name']} but never "
                        f"reached {config['cameras'][later_cam]['name']} "
                        f"(processed, {round(hours_elapsed, 1)}h elapsed)"
                    )
                    if not db.alert_exists(plate, "route_anomaly", msg):
                        db.insert_alert(plate, "route_anomaly", msg)


def run_all_checks_for_plate(plate):
    check_blacklist(plate)
    check_speeding(plate)


def run_global_checks():
    check_route_anomalies()
