"""
geo.py
Small helper for turning two (lat, lon) points into a real-world distance,
and turning distance + time into a speed. This is the "haversine formula" -
the standard way to measure distance between two GPS points on a sphere.
"""

import math


def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0  # Earth's radius in km
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def compute_leg(det_a, det_b):
    """Given two detection rows (dicts) for the SAME plate at two cameras,
    return distance (km), travel time (hours), and average speed (km/h)."""
    dist_km = haversine_km(det_a["lat"], det_a["lon"], det_b["lat"], det_b["lon"])
    time_sec = abs(det_b["timestamp"] - det_a["timestamp"])
    time_hr = time_sec / 3600.0
    speed_kmh = dist_km / time_hr if time_hr > 0 else 0
    return {
        "from_camera": det_a["camera_name"],
        "to_camera": det_b["camera_name"],
        "distance_km": round(dist_km, 2),
        "travel_time_min": round(time_sec / 60.0, 1),
        "speed_kmh": round(speed_kmh, 1),
    }
