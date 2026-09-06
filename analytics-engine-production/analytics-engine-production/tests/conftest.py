"""Test fixtures.

Sets environment variables BEFORE the app is imported so tests run on a
throwaway SQLite database (no PostgreSQL needed), with API-key auth enabled.
"""
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

# --- Configure environment before importing the app ---
_TMP_DB = Path(tempfile.gettempdir()) / "anpr_test.db"
if _TMP_DB.exists():
    _TMP_DB.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{_TMP_DB}"
os.environ["ANALYTICS_API_KEY"] = "test-secret-key-123"
os.environ["DENSITY_LOW_THRESHOLD"] = "5"
os.environ["DENSITY_HIGH_THRESHOLD"] = "15"
os.environ["CONGESTION_THRESHOLD"] = "1.5"

from fastapi.testclient import TestClient  # noqa: E402

from app.database import SessionLocal, init_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Camera, PlateEvent, TrafficBaseline  # noqa: E402

API_KEY = {"X-API-Key": "test-secret-key-123"}


@pytest.fixture(scope="session")
def client():
    init_db()
    _seed()
    with TestClient(app) as c:
        yield c


def _seed() -> None:
    """Insert a small deterministic dataset for assertions."""
    db = SessionLocal()
    now = datetime.utcnow()

    # Cameras. SQLite mirror stores location as 'lng lat'.
    cams = [
        Camera(name="CAM Alpha", location="77.3240 28.1449", rtsp_url="r1"),
        Camera(name="CAM Beta", location="77.3350 28.1600", rtsp_url="r2"),
        Camera(name="CAM Gamma", location="77.3100 28.0900", rtsp_url="r3"),
    ]
    db.add_all(cams)
    db.flush()
    c1, c2, c3 = cams[0].id, cams[1].id, cams[2].id

    def add(plate, cam_id, mins_ago, conf=0.95, dup=False):
        when = now - timedelta(minutes=mins_ago)
        db.add(PlateEvent(plate_number=plate, camera_id=cam_id,
                          event_time=when, confidence=conf))
        if dup:
            # exact duplicate (same plate/camera/time)
            db.add(PlateEvent(plate_number=plate, camera_id=cam_id,
                              event_time=when, confidence=conf))

    # Journeys (within last hour):
    #   PLATE1: c1 -> c2 (two transitions start)
    #   PLATE2: c1 -> c2 -> c3
    #   PLATE3: c2 (stays at c2, repeated frames -> no movement)
    add("PLATE1", c1, 50)
    add("PLATE1", c2, 40)
    add("PLATE2", c1, 45)
    add("PLATE2", c2, 30, dup=True)   # duplicate frame at c2
    add("PLATE2", c2, 29)            # repeated same-camera frame
    add("PLATE2", c3, 15)
    add("PLATE3", c2, 20)
    add("PLATE3", c2, 10)            # same camera again -> NOT a transition
    # Extra distinct vehicles to pad counts.
    for i in range(10):
        add(f"PAD{i}", c2, i + 1)    # many at c2 -> HIGH
    for i in range(3):
        add(f"LOW{i}", c3, i + 1)    # few at c3
    # An event at an unknown camera id (no cameras row).
    add("GHOST", 9999, 5)
    # One old event (3 hours ago) for trend/history.
    db.add(PlateEvent(plate_number="OLD", camera_id=c1,
                      event_time=now - timedelta(hours=3), confidence=0.9))

    # Baselines: c1 low, c2 normal-ish, c3 with NO baseline.
    db.add_all([
        TrafficBaseline(camera_id=c1, time_period="1h", average_vehicle_count=50),
        TrafficBaseline(camera_id=c2, time_period="1h", average_vehicle_count=5),
    ])
    db.commit()
    db.close()
