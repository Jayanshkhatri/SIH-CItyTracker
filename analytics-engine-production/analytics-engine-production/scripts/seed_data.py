"""Seed sample ANPR data into the EXISTING database tables.

SAFETY:
  * This script never creates `cameras` or `plate_events` (they already
    exist). It only INSERTs sample rows.
  * It is idempotent: if the tables already contain data, it stops and
    changes nothing - so it is safe to run against a real database.
  * It creates/updates ONLY the engine-owned `traffic_baselines` table.

PostGIS note:
  On PostgreSQL the camera point is inserted as a real geography:
      ST_SetSRID(ST_MakePoint(lng, lat), 4326)::geography
  On the local SQLite mirror it is stored as the text 'lng lat'.

Run:  python scripts/seed_data.py
"""
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Allow running as `python scripts/seed_data.py` from the project root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import func, select, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.database import SessionLocal, init_db  # noqa: E402
from app.models import Camera, PlateEvent, TrafficBaseline  # noqa: E402

random.seed(42)  # deterministic sample data

# Camera sample data (around Palwal, Haryana). (lat, lng)
CAMERAS = [
    ("Palwal Toll Plaza", 28.1449, 77.3240, "rtsp://cam01/stream"),
    ("NH-44 Junction", 28.1600, 77.3350, "rtsp://cam02/stream"),
    ("Hodal Crossing", 28.0900, 77.3100, "rtsp://cam03/stream"),
    ("Railway Overbridge", 28.1520, 77.3450, "rtsp://cam04/stream"),
    ("Market Chowk", 28.1400, 77.3100, "rtsp://cam05/stream"),
    ("Industrial Area Gate", 28.1750, 77.3550, "rtsp://cam06/stream"),
]

# Mock baselines (normal distinct vehicles in 1 hour) per camera, in order.
BASELINES_1H = [20, 25, 15, 30, 12, 18]

# Approximate distinct vehicles we want in the LAST HOUR per camera
# (chosen so some cameras are clearly CONGESTED vs their baseline).
TARGET_LAST_HOUR = [40, 30, 8, 46, 22, 10]


def _insert_cameras(db: Session) -> list[int]:
    """Insert cameras (only on an empty table) and return their ids."""
    existing = db.execute(select(func.count(Camera.id))).scalar_one()
    if existing:
        ids = list(db.execute(select(Camera.id).order_by(Camera.id)).scalars().all())
        print(f"cameras already has {existing} rows - reusing existing ids.")
        return ids

    ids: list[int] = []
    is_sqlite = get_settings().is_sqlite
    for name, lat, lng, rtsp in CAMERAS:
        if is_sqlite:
            cam = Camera(name=name, location=f"{lng} {lat}", rtsp_url=rtsp)
            db.add(cam)
            db.flush()
            ids.append(cam.id)
        else:
            # Real PostGIS geography point.
            sql = text(
                """
                INSERT INTO cameras (name, location, rtsp_url)
                VALUES (:name,
                        ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography,
                        :rtsp)
                RETURNING id
                """
            )
            new_id = db.execute(
                sql, {"name": name, "lng": lng, "lat": lat, "rtsp": rtsp}
            ).scalar_one()
            ids.append(new_id)
    db.commit()
    print(f"Inserted {len(ids)} cameras.")
    return ids


def _add_event(db, plate, camera_id, when, confidence):
    db.add(
        PlateEvent(
            plate_number=plate,
            camera_id=camera_id,
            event_time=when.replace(tzinfo=None),  # naive UTC
            confidence=round(confidence, 3),
        )
    )


def _plate(prefix: str, n: int) -> str:
    return f"{prefix}{n:04d}"


def seed_events(db: Session, cam_ids: list[int]) -> int:
    now = datetime.utcnow()
    count = 0

    def rand_time_within_last_hour():
        return now - timedelta(minutes=random.randint(0, 59), seconds=random.randint(0, 59))

    # 1) Corridor journeys -> demonstrates OD analysis.
    #    Route A: cam1 -> cam2 -> cam4 -> cam6  (12 vehicles)
    for i in range(12):
        plate = _plate("HR26A", i)
        t = now - timedelta(minutes=random.randint(5, 55))
        route = [0, 1, 3, 5]
        for step, cam_index in enumerate(route):
            when = t + timedelta(minutes=8 * step)
            _add_event(db, plate, cam_ids[cam_index], when, random.uniform(0.85, 0.99))
            # Add a repeated same-camera frame (must NOT create fake movement).
            if step == 1 and i % 2 == 0:
                _add_event(db, plate, cam_ids[cam_index], when + timedelta(seconds=20),
                           random.uniform(0.8, 0.95))
            count += 1

    #    Route B: cam3 -> cam1 -> cam2  (6 vehicles)
    for i in range(6):
        plate = _plate("HR26B", i)
        t = now - timedelta(minutes=random.randint(10, 50))
        for step, cam_index in enumerate([2, 0, 1]):
            _add_event(db, plate, cam_ids[cam_index], t + timedelta(minutes=7 * step),
                       random.uniform(0.8, 0.98))
            count += 1

    #    Route C: cam5 -> cam1  (4 vehicles)
    for i in range(4):
        plate = _plate("HR26C", i)
        t = now - timedelta(minutes=random.randint(5, 45))
        for step, cam_index in enumerate([4, 0]):
            _add_event(db, plate, cam_ids[cam_index], t + timedelta(minutes=6 * step),
                       random.uniform(0.82, 0.97))
            count += 1

    # 2) Extra single-camera volume per camera to hit the target counts.
    #    (Plates above already contribute some; we top up with unique plates.)
    plate_counter = 1000
    for cam_index, target in enumerate(TARGET_LAST_HOUR):
        for _ in range(target):
            plate = _plate("HRV", plate_counter)
            plate_counter += 1
            when = rand_time_within_last_hour()
            _add_event(db, plate, cam_ids[cam_index], when, random.uniform(0.7, 0.99))
            # Occasionally emit an EXACT duplicate (same plate/camera/time).
            if plate_counter % 37 == 0:
                _add_event(db, plate, cam_ids[cam_index], when, random.uniform(0.7, 0.99))
            count += 1

    # 3) A handful of older events (earlier today) so trends over 3h vary.
    for _ in range(120):
        cam_index = random.randrange(len(cam_ids))
        plate = _plate("HRO", plate_counter)
        plate_counter += 1
        when = now - timedelta(hours=random.randint(1, 3), minutes=random.randint(0, 59))
        _add_event(db, plate, cam_ids[cam_index], when, random.uniform(0.7, 0.98))
        count += 1

    db.commit()
    return count


def seed_baselines(db: Session, cam_ids: list[int]) -> None:
    """Insert mock baselines (our table) - safe to run repeatedly."""
    for cam_id, avg in zip(cam_ids, BASELINES_1H):
        existing = db.execute(
            select(TrafficBaseline).where(
                TrafficBaseline.camera_id == cam_id,
                TrafficBaseline.time_period == "1h",
            )
        ).scalar_one_or_none()
        if existing is None:
            db.add(
                TrafficBaseline(
                    camera_id=cam_id, time_period="1h", average_vehicle_count=float(avg)
                )
            )
    db.commit()
    print("Upserted mock baselines (time_period='1h').")


def main() -> None:
    init_db()  # creates traffic_baselines (and SQLite mirror tables)
    db = SessionLocal()
    try:
        already = db.execute(select(func.count(PlateEvent.id))).scalar_one()
        if already:
            print(f"plate_events already has {already} rows - nothing to seed. "
                  "Skipping to avoid duplicate data.")
            return

        cam_ids = _insert_cameras(db)
        n = seed_events(db, cam_ids)
        seed_baselines(db, cam_ids)
        print(f"Done. Inserted {n} plate_events across {len(cam_ids)} cameras.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
