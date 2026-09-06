"""Step 2.37 — production-compatible camera road-network representation.

This is an additive adapter: ``trajectory.py`` remains the verified temporary
graph implementation.  The adapter can represent that graph with Haversine
fallbacks today and explicit directed network measurements in production.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import heapq
from typing import Any

import trajectory_engine as engine
import trajectory_repository as phase7


@dataclass(frozen=True)
class RoadNetworkConnection:
    """One directed, explainable connection between two camera locations."""

    connection_id: str
    source_camera: str
    destination_camera: str
    segment_id: str
    direction: str
    distance_km: float | None = None
    expected_travel_seconds: float | None = None
    speed_limit_kmh: float | None = None
    enabled: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not all((self.connection_id, self.source_camera, self.destination_camera, self.segment_id, self.direction)):
            raise ValueError("Network connection identity fields must be non-empty")
        if self.distance_km is not None and self.distance_km < 0:
            raise ValueError("distance_km cannot be negative")
        if self.expected_travel_seconds is not None and self.expected_travel_seconds <= 0:
            raise ValueError("expected_travel_seconds must be positive")
        if self.speed_limit_kmh is not None and self.speed_limit_kmh <= 0:
            raise ValueError("speed_limit_kmh must be positive")


class ProductionCameraNetwork:
    """Dijkstra routing over directed, enabled road-network connections."""

    def __init__(self, cameras: dict[str, dict[str, float]]) -> None:
        self.cameras = cameras
        self._outgoing: dict[str, list[RoadNetworkConnection]] = {
            camera: [] for camera in cameras
        }

    def add_connection(self, connection: RoadNetworkConnection) -> None:
        if connection.source_camera not in self.cameras or connection.destination_camera not in self.cameras:
            raise ValueError("Connection cameras must exist in the network")
        self._outgoing[connection.source_camera].append(connection)
        self._outgoing[connection.source_camera].sort(key=lambda item: item.connection_id)

    @classmethod
    def from_development_graph(cls) -> "ProductionCameraNetwork":
        """Represent the existing bidirectional development graph without changing it."""
        network = cls(engine.CAMERAS)
        for source in sorted(engine.CAMERA_GRAPH):
            for destination in sorted(engine.CAMERA_GRAPH[source]):
                network.add_connection(RoadNetworkConnection(
                    connection_id=f"DEV:{source}->{destination}",
                    source_camera=source,
                    destination_camera=destination,
                    segment_id=f"DEV_SEGMENT:{source}:{destination}",
                    direction=f"{source}->{destination}",
                    metadata={"distance_source": "HAVERSINE_DEVELOPMENT"},
                ))
        return network

    def route(self, source_camera: str, destination_camera: str) -> dict[str, Any]:
        """Return an explainable minimum-distance route or the legacy no-path state."""
        if source_camera not in self.cameras or destination_camera not in self.cameras:
            raise ValueError("Unknown source or destination camera")
        if source_camera == destination_camera:
            return self._result("CONNECTED", source_camera, destination_camera, [source_camera], [], 0.0)

        queue: list[tuple[float, tuple[str, ...], str, list[RoadNetworkConnection]]] = [
            (0.0, (source_camera,), source_camera, [])
        ]
        best: dict[str, tuple[float, tuple[str, ...]]] = {source_camera: (0.0, (source_camera,))}
        while queue:
            distance, path, current, connections = heapq.heappop(queue)
            if best.get(current) != (distance, path):
                continue
            if current == destination_camera:
                return self._result("CONNECTED", source_camera, destination_camera, list(path), connections, distance)
            for connection in self._outgoing[current]:
                if not connection.enabled:
                    continue
                edge_distance = self._edge_distance(connection)
                candidate = (distance + edge_distance, path + (connection.destination_camera,))
                previous = best.get(connection.destination_camera)
                if previous is None or candidate < previous:
                    best[connection.destination_camera] = candidate
                    heapq.heappush(queue, (candidate[0], candidate[1], connection.destination_camera, connections + [connection]))
        return {"status": "NO CONNECTED PATH", "source_camera": source_camera, "destination_camera": destination_camera, "camera_sequence": [], "connections": [], "distance_km": None, "expected_travel_seconds": None, "speed_limit_kmh": []}

    def _edge_distance(self, connection: RoadNetworkConnection) -> float:
        if connection.distance_km is not None:
            return connection.distance_km
        source, destination = self.cameras[connection.source_camera], self.cameras[connection.destination_camera]
        return engine.haversine_distance_km(source["lat"], source["lon"], destination["lat"], destination["lon"])

    def _result(self, status: str, source: str, destination: str, cameras: list[str], connections: list[RoadNetworkConnection], distance: float) -> dict[str, Any]:
        expected = 0.0
        has_expected = bool(connections)
        for connection in connections:
            if connection.expected_travel_seconds is not None:
                expected += connection.expected_travel_seconds
            elif connection.speed_limit_kmh:
                expected += self._edge_distance(connection) / connection.speed_limit_kmh * 3600
            else:
                has_expected = False
        return {"status": status, "source_camera": source, "destination_camera": destination, "camera_sequence": cameras, "connections": [asdict(item) for item in connections], "distance_km": distance, "expected_travel_seconds": expected if has_expected else None, "speed_limit_kmh": [item.speed_limit_kmh for item in connections], "distance_sources": [item.metadata.get("distance_source", "EXPLICIT_NETWORK") if item.distance_km is None else "EXPLICIT_NETWORK" for item in connections]}


def verify_network() -> bool:
    network = ProductionCameraNetwork.from_development_graph()
    normal = network.route("Camera_1", "Camera_3")
    disconnected = network.route("Camera_1", "Camera_5")
    development_pass = normal["status"] == "CONNECTED" and normal["camera_sequence"] == ["Camera_1", "Camera_2", "Camera_3"] and normal["distance_km"] is not None and disconnected["status"] == "NO CONNECTED PATH" and disconnected["distance_km"] is None

    cameras = {key: {"lat": 0.0, "lon": 0.0} for key in ("A", "B", "C", "D")}
    alternative = ProductionCameraNetwork(cameras)
    for source, destination in (("A", "B"), ("B", "D"), ("A", "C"), ("C", "D")):
        alternative.add_connection(RoadNetworkConnection(f"{source}{destination}", source, destination, f"S_{source}{destination}", f"{source}->{destination}", distance_km=1.0))
    alternative_pass = alternative.route("A", "D")["camera_sequence"] == ["A", "B", "D"]
    direction_pass = alternative.route("B", "A")["status"] == "NO CONNECTED PATH"

    explicit = ProductionCameraNetwork({"A": {"lat": 0.0, "lon": 0.0}, "B": {"lat": 1.0, "lon": 1.0}})
    explicit.add_connection(RoadNetworkConnection("AB", "A", "B", "ROAD_1", "EASTBOUND", distance_km=1.25, expected_travel_seconds=120, speed_limit_kmh=45, metadata={"road_name": "Test Road"}))
    explicit_result = explicit.route("A", "B")
    metadata_pass = explicit_result["distance_km"] == 1.25 and explicit_result["expected_travel_seconds"] == 120 and explicit_result["speed_limit_kmh"] == [45] and explicit_result["connections"][0]["direction"] == "EASTBOUND"
    regression_pass = phase7.verify_phase7()
    checks = {"Normal/development route": development_pass, "Deterministic alternative route": alternative_pass, "Directed connection": direction_pass, "Explicit network metadata": metadata_pass, "Step 2.30-2.36 regression": regression_pass}
    print("\nSTEP 2.37 VERIFICATION")
    for name, passed in checks.items(): print(f"{name}: {'PASS' if passed else 'FAIL'}")
    return all(checks.values())


if __name__ == "__main__":
    raise SystemExit(0 if verify_network() else 1)
