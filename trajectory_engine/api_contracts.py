"""Stable JSON/GIS contract for the existing trajectory intelligence output.

Development camera coordinates are labelled as fixtures.  No line geometry is
invented: a GeoJSON LineString contains only ordered camera observation points.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

CONTRACT_VERSION = "2.44"
COORDINATE_REFERENCE = "WGS84"


class ContractError(ValueError):
    """Raised when dashboard/GIS input is incomplete or inconsistent."""


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def pagination(items: list[Any], offset: int = 0, limit: int = 100) -> dict[str, Any]:
    if offset < 0 or limit < 1 or limit > 1000:
        raise ContractError("offset must be non-negative and limit must be 1..1000")
    return {"items": items[offset:offset + limit], "pagination": {
        "offset": offset, "limit": limit, "total": len(items),
        "next_offset": offset + limit if offset + limit < len(items) else None,
    }}


def error(code: str, message: str, request_id: str | None = None,
          details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"contract_version": CONTRACT_VERSION, "error": {
        "code": code, "message": message, "request_id": request_id,
        "details": details or {},
    }}


def alert_resource(alert: dict[str, Any]) -> dict[str, Any]:
    """Serialize persisted PUC alerts safely while retaining Phase 8 fields."""
    if alert.get("alert_source") != "PUC":
        return alert
    return {"alert_source": "PUC", "alert_id": alert.get("alert_id"),
            "plate_number": alert.get("plate_number"), "alert_type": alert.get("alert_type"),
            "severity": alert.get("severity"), "message": alert.get("message"),
            "is_resolved": alert.get("is_resolved")}


def camera_feature(camera_id: str, camera: dict[str, Any]) -> dict[str, Any]:
    lat, lon = camera.get("lat"), camera.get("lon")
    geometry = None if lat is None or lon is None else {
        "type": "Point", "coordinates": [float(lon), float(lat)],
    }
    return {"type": "Feature", "geometry": geometry, "properties": {
        "camera_id": camera_id, "camera_name": camera.get("name", camera_id),
        "source_camera_id": camera.get("id", camera_id),
        "coordinate_reference": COORDINATE_REFERENCE,
        "coordinate_provenance": camera.get("coordinate_provenance", "DEVELOPMENT_FIXTURE"),
    }}


def trajectory_feature(record: dict[str, Any], cameras: dict[str, dict[str, Any]]) -> dict[str, Any]:
    events = [a["event"] for a in record["associations"] if a.get("event")]
    coordinates = []
    for event in events:
        camera = cameras.get(event.get("camera_id"), {})
        if camera.get("lat") is not None and camera.get("lon") is not None:
            coordinates.append([float(camera["lon"]), float(camera["lat"])])
    geometry = {"type": "LineString", "coordinates": coordinates} if len(coordinates) >= 2 else None
    return {"type": "Feature", "geometry": geometry, "properties": {
        "trajectory_id": record["trajectory_id"],
        "camera_sequence": record["identity"]["camera_sequence"],
        "geometry_provenance": "ORDERED_CAMERA_OBSERVATIONS_NOT_ROAD_GEOMETRY",
        "coordinate_reference": COORDINATE_REFERENCE,
    }}


def _events(record: dict[str, Any], cameras: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    output = []
    for association in record["associations"]:
        event = association.get("event")
        if not event:
            continue
        camera = cameras.get(event.get("camera_id"), {})
        output.append({"event_id": event.get("id"), "timestamp": event.get("timestamp"),
            "event_timestamp": event.get("event_timestamp"), "event_date": event.get("event_date"),
            "camera_id": event.get("camera_id"), "camera_name": camera.get("name", event.get("camera_id")),
            "plate_observation": event.get("plate_number"), "ocr_confidence": event.get("confidence"),
            "association": {"status": association.get("status"), "decision": association.get("decision"),
                            "confidence": association.get("confidence")}})
    return output


def trajectory_resource(record: dict[str, Any], movement: dict[str, Any] | None,
                        alerts: Iterable[dict[str, Any]], cameras: dict[str, dict[str, Any]]) -> dict[str, Any]:
    identity, events = record["identity"], _events(record, cameras)
    relevant_alerts = [a for a in alerts if a.get("trajectory_id") == record["trajectory_id"]]
    return {"trajectory_id": record["trajectory_id"], "vehicle_identity": {
        "primary_plate": identity["primary_plate"], "observed_plates": identity["observed_plates"],
        "identity_status": identity.get("identity_status", "IN_MEMORY"),
    }, "events": events, "camera_sequence": identity["camera_sequence"],
        "start_timestamp": events[0]["timestamp"] if events else None,
        "end_timestamp": events[-1]["timestamp"] if events else None,
        "origin_camera_id": movement.get("first_camera") if movement else None,
        "destination_camera_id": movement.get("last_camera") if movement else None,
        "movement": movement or {}, "quality": {"score": identity["quality_score"],
            "level": identity["quality_level"], "usability": identity["usability"]},
        "lifecycle": record["lifecycle"], "alerts": relevant_alerts,
        "gis_feature": trajectory_feature(record, cameras)}


def dashboard_document(trajectories: list[dict[str, Any]], flows: list[dict[str, Any]],
                       travel_times: list[dict[str, Any]], congestion: list[dict[str, Any]],
                       routes: list[dict[str, Any]], alerts: list[dict[str, Any]],
                       cameras: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {"contract_version": CONTRACT_VERSION, "generated_at": iso_now(),
        "coordinate_reference": COORDINATE_REFERENCE,
        "development_fixture_notice": "Camera coordinates/network may be development fixtures, not production roads.",
        "summary": {"trajectory_count": len(trajectories), "alert_count": len(alerts),
                    "flow_count": len(flows), "congestion_count": len(congestion)},
        "trajectories": trajectories, "analytics": {"flows": flows, "travel_times": travel_times,
            "congestion": congestion, "origin_destinations": routes, "alerts": alerts},
        "gis": {"camera_features": {"type": "FeatureCollection", "features": [camera_feature(k, v) for k, v in sorted(cameras.items())]},
                "trajectory_features": {"type": "FeatureCollection", "features": [t["gis_feature"] for t in trajectories]}}}


def validate_document(document: dict[str, Any]) -> bool:
    if document.get("contract_version") != CONTRACT_VERSION:
        raise ContractError("Unsupported dashboard contract version")
    if not isinstance(document.get("trajectories"), list) or not isinstance(document.get("analytics"), dict):
        raise ContractError("Dashboard document is missing required collections")
    for trajectory in document["trajectories"]:
        required = {"trajectory_id", "vehicle_identity", "events", "quality", "lifecycle", "gis_feature"}
        if not required.issubset(trajectory):
            raise ContractError("Trajectory resource is missing contract fields")
    return True
