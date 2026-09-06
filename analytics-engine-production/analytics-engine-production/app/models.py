"""SQLAlchemy models mapped onto the EXISTING team database.

IMPORTANT
---------
These models map to tables your team already created in PostgreSQL:

    cameras       (id, name, location GEOGRAPHY(POINT), rtsp_url)
    plate_events  (id, plate_number, camera_id -> cameras.id,
                   event_time TIMESTAMP, confidence FLOAT)

The Analytics Engine must NOT create, drop, or alter those two tables.
On PostgreSQL the app only *reads* them and creates the single small
`traffic_baselines` table it owns.

(For zero-install local development the engine can use a SQLite file whose
tables mirror this shape; that mirror is created automatically. See
database.init_db.)

Note on `cameras.location`:
  The real column type is PostGIS  GEOGRAPHY(POINT).
  We never read/write it through the ORM - coordinates are fetched with
  PostGIS functions (ST_X / ST_Y) in app/repository.py - so it is declared
  loosely here just so the model matches the table.
"""
from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class Camera(Base):
    """Maps to the existing `cameras` table (READ-ONLY for this engine)."""

    __tablename__ = "cameras"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Real type: GEOGRAPHY(POINT). Accessed only via PostGIS SQL, never ORM.
    location: Mapped[str | None] = mapped_column(Text, nullable=True)
    rtsp_url: Mapped[str | None] = mapped_column(Text, nullable=True)


class PlateEvent(Base):
    """Maps to the existing `plate_events` table (READ-ONLY for this engine).

    One row = one vehicle detection produced by a camera.
    `event_time` is stored as a naive timestamp and treated as UTC.
    """

    __tablename__ = "plate_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plate_number: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    camera_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("cameras.id"), nullable=False, index=True
    )
    event_time: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),  # naive UTC
        index=True,
    )
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    __table_args__ = (
        # Composite indexes that speed up the analytics queries.
        Index("ix_plate_events_camera_time", "camera_id", "event_time"),
        Index("ix_plate_events_plate_time", "plate_number", "event_time"),
    )


class TrafficBaseline(Base):
    """NEW table owned by the Analytics Engine (created only if missing).

    Stores the "normal" number of vehicles a camera sees in a given time
    period, used for congestion detection.

    Why this table is needed:
      Congestion = current traffic vs. historical normal. The existing
      schema has nowhere to store that historical normal, so we add the
      smallest possible table. It never touches the two existing tables.
    """

    __tablename__ = "traffic_baselines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    camera_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("cameras.id"), nullable=False, index=True
    )
    # Period this baseline represents, e.g. "15m", "30m", "1h", "3h".
    time_period: Mapped[str] = mapped_column(String(10), nullable=False, default="1h")
    # Typical number of (distinct) vehicles for that camera in that period.
    average_vehicle_count: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    __table_args__ = (
        UniqueConstraint("camera_id", "time_period", name="uq_baseline_camera_period"),
    )
