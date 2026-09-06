from pathlib import Path
from dataclasses import replace

import pytest

from demo_network import load_demo_network


NETWORK_CONFIG = Path(__file__).parent.parent / "config" / "demo_network.json"


def test_demo_network_loads():
    network = load_demo_network(NETWORK_CONFIG)

    assert network is not None
    assert len(network.cameras) == 8

    connection_count = sum(
        len(items)
        for items in network._outgoing.values()
    )

    assert connection_count == 12


def test_demo_network_camera_names():
    network = load_demo_network(NETWORK_CONFIG)

    assert set(network.cameras.keys()) == {
        "CAM_01",
        "CAM_02",
        "CAM_03",
        "CAM_04",
        "CAM_05",
        "CAM_06",
        "CAM_07",
        "CAM_08",
    }


def test_demo_network_connections_load():
    network = load_demo_network(NETWORK_CONFIG)

    connections = [
        connection
        for items in network._outgoing.values()
        for connection in items
    ]

    assert len(connections) == 12

    connection_ids = {
        connection.connection_id
        for connection in connections
    }

    assert connection_ids == {
        "D01",
        "D02",
        "D03",
        "D04",
        "D05",
        "D06",
        "D07",
        "D08",
        "D09",
        "D10",
        "D11",
        "D12",
    }


def test_demo_network_directed_route():
    network = load_demo_network(NETWORK_CONFIG)

    route = network.route("CAM_01", "CAM_03")

    assert route is not None
    assert route["status"] == "CONNECTED"
    assert route["source_camera"] == "CAM_01"
    assert route["destination_camera"] == "CAM_03"
    assert route["camera_sequence"] == [
        "CAM_01",
        "CAM_02",
        "CAM_03",
    ]
    assert route["distance_km"] == pytest.approx(3.3)
    assert route["expected_travel_seconds"] == pytest.approx(660.0)


def test_demo_network_alternative_route():
    network = load_demo_network(NETWORK_CONFIG)

    route = network.route("CAM_04", "CAM_07")

    assert route is not None
    assert route["status"] == "CONNECTED"
    assert route["source_camera"] == "CAM_04"
    assert route["destination_camera"] == "CAM_07"
    assert route["camera_sequence"] == [
        "CAM_04",
        "CAM_06",
        "CAM_07",
    ]
    assert route["distance_km"] == pytest.approx(4.7)
    assert route["expected_travel_seconds"] == pytest.approx(840.0)

def test_demo_network_reverse_route():
    network = load_demo_network(NETWORK_CONFIG)

    route = network.route("CAM_07", "CAM_01")

    assert route is not None
    assert route["status"] == "CONNECTED"
    assert route["source_camera"] == "CAM_07"
    assert route["destination_camera"] == "CAM_01"
    assert route["camera_sequence"] == [
        "CAM_07",
        "CAM_08",
        "CAM_01",
    ]
    assert route["distance_km"] == pytest.approx(5.5)
    assert route["expected_travel_seconds"] == pytest.approx(1020.0)


def test_demo_network_camera_overrides_can_use_supabase_camera_set():
    network = load_demo_network(
        NETWORK_CONFIG,
        camera_overrides={
            "CAM_01": {
                "name": "CAM_01",
                "lat": 28.6315,
                "lon": 77.2167,
            },
            "CAM_02": {
                "name": "CAM_02",
                "lat": 28.6129,
                "lon": 77.2295,
            },
            "CAM_03": {
                "name": "CAM_03",
                "lat": 28.6519,
                "lon": 77.1909,
            },
            "CAM_04": {
                "name": "CAM_04",
                "lat": 28.6350,
                "lon": 77.2090,
            },
            "CAM_05": {
                "name": "CAM_05",
                "lat": 28.6200,
                "lon": 77.2400,
            },
            "CAM_06": {
                "name": "CAM_06",
                "lat": 28.6400,
                "lon": 77.1800,
            },
        },
    )

    assert set(network.cameras.keys()) == {
        "CAM_01",
        "CAM_02",
        "CAM_03",
        "CAM_04",
        "CAM_05",
        "CAM_06",
    }

    connection_count = sum(
        len(items)
        for items in network._outgoing.values()
    )

    assert connection_count > 0


def test_unavailable_configured_cameras_are_skipped():
    network = load_demo_network(
        NETWORK_CONFIG,
        camera_overrides={
            "CAM_01": {
                "name": "CAM_01",
                "lat": 28.6315,
                "lon": 77.2167,
            },
            "CAM_02": {
                "name": "CAM_02",
                "lat": 28.6129,
                "lon": 77.2295,
            },
        },
    )

    assert set(network.cameras.keys()) == {
        "CAM_01",
        "CAM_02",
    }

    for connections in network._outgoing.values():
        for connection in connections:
            assert connection.source_camera in network.cameras
            assert connection.destination_camera in network.cameras


def test_disabled_connection_is_not_used():
    network = load_demo_network(NETWORK_CONFIG)

    original_connections = [
        connection
        for items in network._outgoing.values()
        for connection in items
    ]

    target = next(
        connection
        for connection in original_connections
        if connection.connection_id == "D01"
    )

    replacement = replace(target, enabled=False)

    source_connections = network._outgoing[target.source_camera]

    for index, connection in enumerate(source_connections):
        if connection.connection_id == target.connection_id:
            source_connections[index] = replacement
            break

    route = network.route("CAM_01", "CAM_03")

    assert route is not None
    assert route["status"] != "CONNECTED" or (
        "CAM_02" not in route.get("camera_sequence", [])
    )


def test_demo_network_metadata():
    network = load_demo_network(NETWORK_CONFIG)

    metadata = network.demo_network_metadata

    assert metadata["network_provenance"] == "DEMO_NETWORK"
    assert metadata["configured_camera_count"] == 8
    assert metadata["active_camera_count"] == 8
    assert metadata["active_connection_count"] == 12
    assert metadata["skipped_connection_count"] == 0


def test_camera_override_coordinates_are_authoritative():
    network = load_demo_network(
        NETWORK_CONFIG,
        camera_overrides={
            "CAM_01": {
                "name": "CAM_01",
                "lat": 99.123,
                "lon": 88.456,
            },
            "CAM_02": {
                "name": "CAM_02",
                "lat": 77.111,
                "lon": 66.222,
            },
        },
    )

    assert set(network.cameras.keys()) == {
        "CAM_01",
        "CAM_02",
    }

    assert network.cameras["CAM_01"]["lat"] == 99.123
    assert network.cameras["CAM_01"]["lon"] == 88.456
    assert network.cameras["CAM_02"]["lat"] == 77.111
    assert network.cameras["CAM_02"]["lon"] == 66.222