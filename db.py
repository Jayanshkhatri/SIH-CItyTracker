"""
db.py
All database logic lives here. We use SQLite because it needs zero setup
(no server to install) - perfect for a first version / demo / hackathon.
If this were going to production with many cameras, you'd swap this for
PostgreSQL, but every function signature below would stay the same.
"""

import sqlite3
import os
import time

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "db", "anpr.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_conn()
    c = conn.cursor()

    # One shared table for every plate reading, from every camera.
    c.execute("""
        CREATE TABLE IF NOT EXISTS detections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plate TEXT NOT NULL,
            camera_id TEXT NOT NULL,
            camera_name TEXT NOT NULL,
            lat REAL NOT NULL,
            lon REAL NOT NULL,
            timestamp REAL NOT NULL,       -- unix epoch seconds, shared global clock
            confidence REAL NOT NULL,
            video_source TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS blacklist (
            plate TEXT PRIMARY KEY,
            reason TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plate TEXT NOT NULL,
            alert_type TEXT NOT NULL,      -- 'blacklist' | 'speeding' | 'route_anomaly'
            message TEXT NOT NULL,
            created_at REAL NOT NULL
        )
    """)

    conn.commit()
    conn.close()


def insert_detection(plate, camera_id, camera_name, lat, lon, timestamp, confidence, video_source):
    conn = get_conn()
    conn.execute(
        """INSERT INTO detections (plate, camera_id, camera_name, lat, lon, timestamp, confidence, video_source)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (plate, camera_id, camera_name, lat, lon, timestamp, confidence, video_source),
    )
    conn.commit()
    conn.close()


def get_all_detections():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM detections ORDER BY timestamp DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_distinct_plates():
    conn = get_conn()
    rows = conn.execute("SELECT DISTINCT plate FROM detections").fetchall()
    conn.close()
    return [r["plate"] for r in rows]


def get_vehicle_detections(plate):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM detections WHERE plate = ? ORDER BY timestamp ASC", (plate,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_processed_cameras():
    """Which camera_ids have at least one video processed."""
    conn = get_conn()
    rows = conn.execute("SELECT DISTINCT camera_id FROM detections").fetchall()
    conn.close()
    return [r["camera_id"] for r in rows]


def get_camera_counts():
    conn = get_conn()
    rows = conn.execute(
        """SELECT camera_id, camera_name, lat, lon, COUNT(*) as count
           FROM detections GROUP BY camera_id"""
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def is_blacklisted(plate):
    conn = get_conn()
    row = conn.execute("SELECT * FROM blacklist WHERE plate = ?", (plate,)).fetchone()
    conn.close()
    return dict(row) if row else None


def add_to_blacklist(plate, reason="manually flagged"):
    conn = get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO blacklist (plate, reason) VALUES (?, ?)", (plate, reason)
    )
    conn.commit()
    conn.close()


def insert_alert(plate, alert_type, message):
    conn = get_conn()
    conn.execute(
        "INSERT INTO alerts (plate, alert_type, message, created_at) VALUES (?, ?, ?, ?)",
        (plate, alert_type, message, time.time()),
    )
    conn.commit()
    conn.close()


def alert_exists(plate, alert_type, message):
    conn = get_conn()
    row = conn.execute(
        "SELECT 1 FROM alerts WHERE plate=? AND alert_type=? AND message=?",
        (plate, alert_type, message),
    ).fetchone()
    conn.close()
    return row is not None


def get_alerts():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM alerts ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]
