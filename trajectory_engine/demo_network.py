"""Flexible, explicit demo camera network for Supabase-backed demonstrations.

The demo network is configuration-driven: camera count can come directly from
Supabase, while directed connections remain configuration-driven. It is
intentionally labelled as demo provenance and must not be mistaken for
authoritative road GIS.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


from network import ProductionCameraNetwork, RoadNetworkConnection


def load_demo_network(
    path: str | Path,
    *,
    camera_overrides: dict[str, dict[str, Any]] | None = None,
) -> ProductionCameraNetwork:
    """Load the synthetic demo network.

    When camera_overrides is provided, the Supabase camera set becomes
    authoritative. The JSON file provides the synthetic directed connections.

    Connections referencing cameras that are not available in Supabase
    are skipped. This allows the same demo configuration to work with
    different camera counts.
    """

    config_path = Path(path)

    payload = json.loads(
        config_path.read_text(encoding="utf-8")
    )

    cameras = payload.get("cameras")
    connections = payload.get("connections")

    if not isinstance(cameras, dict) or not cameras:
        raise ValueError(
            "Demo network must define a non-empty cameras object"
        )

    if not isinstance(connections, list):
        raise ValueError(
            "Demo network must define a connections list"
        )

    # Load cameras from the demo configuration.
    configured_cameras: dict[str, dict[str, float]] = {}

    for camera_id, camera in cameras.items():

        if not isinstance(camera, dict):
            raise ValueError(
                f"Invalid demo camera: {camera_id}"
            )

        try:
            configured_cameras[str(camera_id)] = {
                "lat": float(camera["lat"]),
                "lon": float(camera["lon"]),
            }

        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(
                f"Invalid coordinates for demo camera {camera_id}"
            ) from exc

    # If Supabase cameras are supplied, they are authoritative.
    if camera_overrides is None:

        normalized = configured_cameras

    else:

        if not camera_overrides:
            raise ValueError(
                "Supabase camera overrides must not be empty"
            )

        normalized: dict[str, dict[str, float]] = {}

        for camera_id, camera in camera_overrides.items():

            if not isinstance(camera, dict):
                raise ValueError(
                    f"Invalid Supabase camera override: {camera_id}"
                )

            try:
                normalized[str(camera_id)] = {
                    "lat": float(camera["lat"]),
                    "lon": float(camera["lon"]),
                }

            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(
                    f"Invalid coordinates for Supabase camera {camera_id}"
                ) from exc

    available_cameras = set(normalized)

    network = ProductionCameraNetwork(normalized)

    skipped_connections = 0

    # Add only connections whose cameras actually exist.
    #
    # demo_network.json uses:
    #   source      -> source camera
    #   destination -> destination camera
    #   segment     -> segment ID
    #
    # These are mapped here to the RoadNetworkConnection field names.
    for item in connections:

        if not isinstance(item, dict):
            raise ValueError(
                "Each demo network connection must be an object"
            )

        source_camera = str(
            item.get("source", "")
        )

        destination_camera = str(
            item.get("destination", "")
        )

        if (
            source_camera not in available_cameras
            or destination_camera not in available_cameras
        ):
            skipped_connections += 1
            continue

        metadata = dict(
            item.get("metadata") or {}
        )

        metadata.setdefault(
            "network_provenance",
            "DEMO_NETWORK"
        )

        network.add_connection(
            RoadNetworkConnection(
                connection_id=str(
                    item["connection_id"]
                ),

                source_camera=source_camera,

                destination_camera=destination_camera,

                segment_id=str(
                    item["segment"]
                ),

                direction=str(
                    item["direction"]
                ),

                distance_km=(
                    float(item["distance_km"])
                    if item.get("distance_km") is not None
                    else None
                ),

                expected_travel_seconds=(
                    float(item["expected_travel_seconds"])
                    if item.get("expected_travel_seconds") is not None
                    else None
                ),

                speed_limit_kmh=(
                    float(item["speed_limit_kmh"])
                    if item.get("speed_limit_kmh") is not None
                    else None
                ),

                enabled=bool(
                    item.get("enabled", True)
                ),

                metadata=metadata,
            )
        )

    active_connection_count = sum(
        len(items)
        for items in network._outgoing.values()
    )

    if active_connection_count == 0:
        raise ValueError(
            "Demo network has no usable connections for the available cameras"
        )

    # Runtime diagnostics.
    network.demo_network_metadata = {
        "network_provenance": "DEMO_NETWORK",
        "configured_camera_count": len(
            configured_cameras
        ),
        "active_camera_count": len(
            normalized
        ),
        "active_connection_count": active_connection_count,
        "skipped_connection_count": skipped_connections,
    }

    return network