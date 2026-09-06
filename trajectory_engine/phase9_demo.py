"""Local-only Phase 9 demonstration; no external database access."""
from __future__ import annotations

import json

from phase9_service import build_local_demo_service


def _value(value) -> str:
    """Render existing contract values compactly without altering them."""
    if value is None:
        return "N/A"
    if isinstance(value, float):
        return f"{value:.3f}"
    if isinstance(value, (list, dict)):
        return json.dumps(value, sort_keys=True)
    return str(value)


def _section(title: str) -> None:
    print("\n" + "=" * 96)
    print(title)
    print("=" * 96)


def print_report(document: dict) -> None:
    """Print all actual local-fixture Phase 9 outputs for visual inspection."""
    _section("SIH26127 — PHASE 9 LOCAL DEVELOPMENT-FIXTURE REPORT")
    print(f"Contract version: {document['contract_version']}")
    print(f"Generated at: {document['generated_at']}")
    print(f"Fixture notice: {document['development_fixture_notice']}")
    print(f"Summary: {_value(document['summary'])}")

    _section("TRAJECTORIES")
    for trajectory in document["trajectories"]:
        identity, movement, quality = trajectory["vehicle_identity"], trajectory["movement"], trajectory["quality"]
        print(f"\nTrajectory: {trajectory['trajectory_id']}")
        print(f"  Primary plate: {identity['primary_plate']}")
        print(f"  Observed plates: {_value(identity['observed_plates'])}")
        print(f"  Cameras: {' -> '.join(trajectory['camera_sequence'])}")
        print(f"  Start / end: {trajectory['start_timestamp']} / {trajectory['end_timestamp']}")
        print(f"  Origin / destination: {trajectory['origin_camera_id']} -> {trajectory['destination_camera_id']}")
        print(f"  Duration seconds: {_value(movement.get('duration_seconds'))}")
        print(f"  Network distance km: {_value(movement.get('total_route_distance_km'))}")
        print(f"  Speed avg/min/max km/h: {_value(movement.get('average_speed_kmh'))} / {_value(movement.get('minimum_speed_kmh'))} / {_value(movement.get('maximum_speed_kmh'))}")
        print(f"  Quality/usability: {quality['score']} / {quality['level']} / {quality['usability']}")
        print(f"  Lifecycle: {trajectory['lifecycle']['state']} ({trajectory['lifecycle']['reason']})")
        print(f"  Alert count: {len(trajectory['alerts'])}")
        for event in trajectory["events"]:
            print(f"    Event {event['event_id']}: {event['timestamp']} @ {event['camera_id']} ({event['plate_observation']}, OCR={_value(event['ocr_confidence'])}, association={event['association']['status']})")

    _section("ALERTS / ANOMALIES")
    for alert in document["analytics"]["alerts"]:
        evidence = alert["evidence"]
        print(f"{alert['anomaly_id']} | trajectory={alert['trajectory_id']} | type={alert['anomaly_type']} | severity={alert['severity']} | status={alert['status']}")
        print(f"  cameras: {alert['source_camera']} -> {alert['destination_camera']} | events={_value(alert['event_ids'])}")
        print(f"  reason: {alert['explanation']}")
        print(f"  evidence: {_value(evidence)}")

    _section("CAMERA-TO-CAMERA FLOWS")
    for flow in document["analytics"]["flows"]:
        print(f"{flow['direction']} | traversals={flow['traversal_count']} | unique trajectories={flow['unique_trajectory_count']} | anomalies={flow['anomaly_count']}")
        print(f"  observed: {flow['first_observed']} to {flow['last_observed']} | distance km={_value(flow['network_distance_km'])} | expected seconds={_value(flow['expected_travel_seconds'])}")
        print(f"  times seconds={_value(flow['travel_times_seconds'])} | avg/median={_value(flow['average_travel_seconds'])}/{_value(flow['median_travel_seconds'])} | speeds km/h={_value(flow['speeds_kmh'])} | avg speed={_value(flow['average_speed_kmh'])}")

    _section("TRAVEL-TIME / SPEED ANALYTICS")
    for item in document["analytics"]["travel_times"]:
        print(f"{item['source_camera']} -> {item['destination_camera']} | traversals={item['traversal_count']} | classification={item['classification']}")
        print(f"  travel seconds avg/median/min/max: {_value(item['average_travel_seconds'])} / {_value(item['median_travel_seconds'])} / {_value(item['minimum_travel_seconds'])} / {_value(item['maximum_travel_seconds'])}")
        print(f"  average speed km/h={_value(item['average_speed_kmh'])} | expected seconds={_value(item['expected_travel_seconds'])} | deviation ratio={_value(item['travel_time_deviation_ratio'])}")

    _section("CONGESTION ANALYTICS")
    for item in document["analytics"]["congestion"]:
        print(f"{item['source_camera']} -> {item['destination_camera']} | window={item['window_start']} ({item['window_minutes']} min) | traversals={item['traversal_count']} | avg speed km/h={_value(item['average_speed_kmh'])} | level={item['congestion_level']}")

    _section("ORIGIN-DESTINATION ANALYTICS")
    for item in document["analytics"]["origin_destinations"]:
        print(f"{item['origin_camera']} -> {item['destination_camera']} | count={item['trajectory_count']} | trajectory IDs={_value(item['trajectory_ids'])}")
        print(f"  camera sequence={_value(item['camera_sequence'])} | avg duration seconds={_value(item['average_duration_seconds'])} | avg distance km={_value(item['average_distance_km'])} | anomalies={item['anomaly_count']}")

    _section("DASHBOARD / GIS CONTRACT — REPRESENTATIVE ACTUAL JSON")
    representative = {"contract_version": document["contract_version"], "summary": document["summary"],
                      "trajectory": document["trajectories"][0],
                      "camera_feature": document["gis"]["camera_features"]["features"][0],
                      "trajectory_feature": document["gis"]["trajectory_features"]["features"][0]}
    print(json.dumps(representative, indent=2, sort_keys=True))


def run_demo() -> dict:
    service, directory = build_local_demo_service()
    try:
        document = service.dashboard()
        print_report(document)
        return document
    finally:
        directory.cleanup()


if __name__ == "__main__":
    run_demo()
