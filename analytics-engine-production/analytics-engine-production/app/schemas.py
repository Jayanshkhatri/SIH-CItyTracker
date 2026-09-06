"""Pydantic schemas - the exact JSON shape of every API response."""
from datetime import datetime

from pydantic import BaseModel, Field


# ---- /health ----
class HealthResponse(BaseModel):
    status: str = "ok"
    database: str
    auth_enabled: bool


# ---- /analytics/events ----
class EventOut(BaseModel):
    id: int
    plate_number: str
    camera_id: int
    camera_name: str | None = None
    event_time: datetime
    confidence: float | None = None


class EventsResponse(BaseModel):
    start: datetime
    end: datetime
    window_label: str | None = None
    total_events: int
    unique_vehicles: int
    events: list[EventOut]


# ---- /analytics/density ----
class CameraDensity(BaseModel):
    camera_id: int
    camera_name: str
    vehicle_count: int       # distinct plates for that camera in the window
    traffic_level: str       # LOW / MEDIUM / HIGH


class DensityResponse(BaseModel):
    start: datetime
    end: datetime
    window_label: str | None = None
    definition: str
    thresholds: dict[str, int]
    total_vehicles: int
    camera_count: int
    cameras: list[CameraDensity]


# ---- /analytics/od ----
class ODPair(BaseModel):
    origin_camera: int
    origin_camera_name: str
    destination_camera: int
    destination_camera_name: str
    vehicle_count: int


class ODResponse(BaseModel):
    start: datetime
    end: datetime
    window_label: str | None = None
    total_transitions: int
    vehicles_with_journey: int
    note: str
    pairs: list[ODPair]


# ---- /analytics/heatmap ----
class HeatmapPoint(BaseModel):
    camera_id: int
    camera_name: str
    latitude: float | None
    longitude: float | None
    vehicle_count: int
    traffic_level: str


class HeatmapResponse(BaseModel):
    start: datetime
    end: datetime
    window_label: str | None = None
    points: list[HeatmapPoint]
    unknown_camera_ids: list[int] = []


# ---- /analytics/congestion ----
class CongestionPoint(BaseModel):
    camera_id: int
    camera_name: str
    current_count: int
    baseline_count: float
    ratio: float
    percent_increase: float | None
    congestion_status: str  # NORMAL / CONGESTED / NO_BASELINE


class CongestionResponse(BaseModel):
    start: datetime
    end: datetime
    window_label: str | None = None
    threshold_ratio: float
    period: str
    baseline_source: str
    points: list[CongestionPoint]


# ---- /analytics/trends ----
class TrendBucket(BaseModel):
    bucket_start: datetime
    bucket_end: datetime
    total_events: int
    unique_vehicles: int
    per_camera: dict[str, int] | None = None


class TrendsResponse(BaseModel):
    start: datetime
    end: datetime
    window_label: str | None = None
    bucket_minutes: int
    bucket_count: int
    buckets: list[TrendBucket]


# ---- errors ----
class ErrorResponse(BaseModel):
    detail: str
