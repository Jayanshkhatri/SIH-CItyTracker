"""End-to-end API tests (time window, density, OD, heatmap, congestion,
trends and API-key authentication)."""
from conftest import API_KEY


def test_health_open(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["database"] == "connected"
    assert body["auth_enabled"] is True


# ---- Authentication ----
def test_no_key_rejected(client):
    r = client.get("/analytics/density")
    assert r.status_code == 401


def test_bad_key_rejected(client):
    r = client.get("/analytics/density", headers={"X-API-Key": "wrong"})
    assert r.status_code == 403


def test_good_key_accepted(client):
    r = client.get("/analytics/density", headers=API_KEY)
    assert r.status_code == 200


# ---- Time window ----
def test_events_default_window(client):
    r = client.get("/analytics/events?window=1h", headers=API_KEY)
    assert r.status_code == 200
    body = r.json()
    assert body["window_label"] == "1h"
    # OLD event (3h ago) must NOT appear; GHOST is within the hour.
    plates = {e["plate_number"] for e in body["events"]}
    assert "OLD" not in plates
    assert "PLATE1" in plates


def test_custom_time_window(client):
    r = client.get(
        "/analytics/events?window=1h", headers=API_KEY
    )
    end = r.json()["end"]
    # A window entirely in the far past returns zero events.
    past = "2000-01-01T00:00:00Z"
    r2 = client.get(
        f"/analytics/events?start={past}&end=2000-01-01T01:00:00Z",
        headers=API_KEY,
    )
    assert r2.status_code == 200
    assert r2.json()["total_events"] == 0
    assert end  # end parsed fine


def test_bad_window_rejected(client):
    r = client.get("/analytics/events?window=99x", headers=API_KEY)
    assert r.status_code == 400


# ---- Density / counting ----
def test_density_counts_distinct_vehicles(client):
    r = client.get("/analytics/density?window=1h", headers=API_KEY)
    cams = {c["camera_id"]: c for c in r.json()["cameras"]}
    # c2 has PLATE1, PLATE2, PLATE3 + 10 PAD = 13 distinct; duplicates ignored.
    beta = next(c for c in r.json()["cameras"] if c["camera_name"] == "CAM Beta")
    assert beta["vehicle_count"] == 13
    assert beta["traffic_level"] in {"LOW", "MEDIUM", "HIGH"}
    # high count -> HIGH (threshold high=15? 13 -> MEDIUM). Assert deterministic.
    assert beta["traffic_level"] == "MEDIUM"


def test_density_unknown_camera_present(client):
    # Unknown camera 9999 still counted in density (no cameras row needed).
    r = client.get("/analytics/density?window=1h", headers=API_KEY)
    ids = {c["camera_id"] for c in r.json()["cameras"]}
    assert 9999 in ids


# ---- OD ----
def test_od_transitions(client):
    r = client.get("/analytics/od?window=1h", headers=API_KEY)
    body = r.json()
    pairs = {(p["origin_camera"], p["destination_camera"]): p["vehicle_count"]
             for p in body["pairs"]}
    # PLATE1 and PLATE2 both do c1 -> c2.
    alpha_to_beta = [p for p in body["pairs"]
                     if p["origin_camera_name"] == "CAM Alpha"
                     and p["destination_camera_name"] == "CAM Beta"]
    assert alpha_to_beta and alpha_to_beta[0]["vehicle_count"] == 2
    # PLATE3 stays at c2 -> no c2->c2 self transition.
    self_pairs = [p for p in body["pairs"]
                  if p["origin_camera"] == p["destination_camera"]]
    assert self_pairs == []
    assert body["vehicles_with_journey"] >= 2


# ---- Heatmap ----
def test_heatmap_structure(client):
    r = client.get("/analytics/heatmap?window=1h", headers=API_KEY)
    body = r.json()
    pts = body["points"]
    # Only the 3 known cameras are mapped; each has coordinates.
    assert len(pts) == 3
    for p in pts:
        assert isinstance(p["latitude"], float)
        assert isinstance(p["longitude"], float)
        assert "traffic_level" in p
    # Unknown camera reported separately, not mapped.
    assert 9999 in body["unknown_camera_ids"]


# ---- Congestion ----
def test_congestion_flags(client):
    r = client.get("/analytics/congestion?window=1h&period=1h", headers=API_KEY)
    body = r.json()
    by_name = {p["camera_name"]: p for p in body["points"]}

    # CAM Beta: ~13 current vs baseline 5 -> ratio ~2.6 -> CONGESTED.
    beta = by_name["CAM Beta"]
    assert beta["congestion_status"] == "CONGESTED"
    assert beta["ratio"] >= 1.5
    assert beta["percent_increase"] is not None

    # CAM Alpha: 2 current vs baseline 50 -> NORMAL.
    alpha = by_name["CAM Alpha"]
    assert alpha["congestion_status"] == "NORMAL"

    # CAM Gamma: no baseline row -> NO_BASELINE.
    gamma = by_name["CAM Gamma"]
    assert gamma["congestion_status"] == "NO_BASELINE"
    assert gamma["percent_increase"] is None


# ---- Trends ----
def test_trends_buckets(client):
    r = client.get(
        "/analytics/trends?window=1h&bucket_minutes=15", headers=API_KEY
    )
    body = r.json()
    assert body["bucket_minutes"] == 15
    assert body["bucket_count"] == 4
    total = sum(b["total_events"] for b in body["buckets"])
    # Counts across buckets should equal the events in the 1h window.
    r_events = client.get("/analytics/events?window=1h", headers=API_KEY).json()
    assert total == r_events["total_events"]


def test_trends_per_camera(client):
    r = client.get(
        "/analytics/trends?window=1h&bucket_minutes=15&per_camera=true",
        headers=API_KEY,
    )
    assert r.status_code == 200
    assert "per_camera" in r.json()["buckets"][0]
