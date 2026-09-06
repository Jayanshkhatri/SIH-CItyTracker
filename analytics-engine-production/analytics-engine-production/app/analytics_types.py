"""Standard in-memory structures used by the analytics algorithms.

The analytics SERVICES only understand these plain objects - they never
import SQLAlchemy. This is the contract that lets the real ANPR database
be swapped in later without touching any analytics logic.

Your ANPR teammate can also feed real detections in as `VehicleEvent`
objects directly (bypassing the database entirely) for unit testing.
"""
from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class VehicleEvent:
    """One vehicle detection in a normalised, database-independent form."""

    plate_number: str
    camera_id: int
    timestamp: datetime          # always timezone-aware UTC
    confidence: float | None = None
    id: int | None = None


@dataclass
class CameraInfo:
    """Camera metadata, including coordinates from the PostGIS location."""

    camera_id: int
    name: str
    latitude: float | None = None
    longitude: float | None = None


@dataclass
class Dataset:
    """Everything an analytics request needs for one time window."""

    events: list[VehicleEvent] = field(default_factory=list)
    cameras: dict[int, CameraInfo] = field(default_factory=dict)
