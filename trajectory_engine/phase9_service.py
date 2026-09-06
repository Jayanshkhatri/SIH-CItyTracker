"""Application service composing verified Phase 7/8 outputs without duplication."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tempfile
from typing import Any

import trajectory as engine
from phase9_contracts import dashboard_document, trajectory_resource, validate_document
from phase9_database import SupabasePucRepository
from phase9_logging import logger, timed
from trajectory_phase7 import Phase7TrajectoryRepository, step_231
from trajectory_phase8 import Phase8Analytics, ProductionCameraNetwork


def development_cameras() -> dict[str, dict[str, Any]]:
    return {key: {**value, "name": key, "coordinate_provenance": "DEVELOPMENT_FIXTURE"}
            for key, value in engine.CAMERAS.items()}


@dataclass
class Phase9Snapshot:
    records: list[dict[str, Any]]
    alerts: list[dict[str, Any]]
    phase8_alerts: list[dict[str, Any]]
    puc_alerts: list[dict[str, Any]]
    movements: list[dict[str, Any]]
    flows: list[dict[str, Any]]
    travel_times: list[dict[str, Any]]
    congestion: list[dict[str, Any]]
    routes: list[dict[str, Any]]


class Phase9Service:
    """Cached, deterministic read model over existing trajectory identities."""
    def __init__(self, repository: Phase7TrajectoryRepository,
                 network: ProductionCameraNetwork | None = None,
                 cameras: dict[str, dict[str, Any]] | None = None,
                 puc_repository: SupabasePucRepository | None = None) -> None:
        self.repository = repository
        self.network = network or ProductionCameraNetwork.from_development_graph()
        self.cameras = cameras or development_cameras()
        self.analytics = Phase8Analytics(self.network)
        self.puc_repository = puc_repository
        self._snapshot: Phase9Snapshot | None = None

    def refresh(self) -> Phase9Snapshot:
        """Compute Phase 8 aggregates once; API reads share this immutable-style snapshot."""
        with timed("phase9_snapshot_refresh"):
            records = self.repository.query()
            phase8_alerts = self.analytics.anomalies(records)
            movements = self.analytics.movement(records, phase8_alerts)
            flows = self.analytics.flows(records, phase8_alerts)
            travel_times = self.analytics.travel_time(flows)
            congestion = self.analytics.congestion(flows)
            routes = self.analytics.routes(records, movements)
            puc_alerts = self.puc_repository.list_puc_alerts() if self.puc_repository else []
            alerts = [self._phase8_alert(item) for item in phase8_alerts] + [self._puc_alert(item) for item in puc_alerts]
            self._snapshot = Phase9Snapshot(records, alerts, phase8_alerts, puc_alerts, movements, flows, travel_times, congestion, routes)
        logger.info("phase9_snapshot_ready trajectories=%s alerts=%s flows=%s", len(records), len(alerts), len(flows))
        return self._snapshot

    def snapshot(self) -> Phase9Snapshot:
        return self._snapshot or self.refresh()

    def trajectory_resources(self) -> list[dict[str, Any]]:
        state = self.snapshot(); movement = {m["trajectory_id"]: m for m in state.movements}
        return [trajectory_resource(record, movement.get(record["trajectory_id"]), state.alerts, self.cameras)
                for record in state.records]

    def trajectory(self, trajectory_id: str) -> dict[str, Any] | None:
        return next((item for item in self.trajectory_resources() if item["trajectory_id"] == trajectory_id), None)

    def dashboard(self) -> dict[str, Any]:
        state = self.snapshot()
        document = dashboard_document(self.trajectory_resources(), state.flows, state.travel_times,
                                      state.congestion, state.routes, state.alerts, self.cameras)
        validate_document(document)
        return document

    def filter_trajectories(self, *, plate: str | None = None, camera: str | None = None,
                            lifecycle_state: str | None = None, usability: str | None = None) -> list[dict[str, Any]]:
        results = self.trajectory_resources()
        if plate:
            normalized = engine.normalize_plate_number(plate)
            results = [x for x in results if normalized in x["vehicle_identity"]["observed_plates"]]
        if camera:
            results = [x for x in results if camera in x["camera_sequence"]]
        if lifecycle_state:
            results = [x for x in results if x["lifecycle"]["state"] == lifecycle_state]
        if usability:
            results = [x for x in results if x["quality"]["usability"] == usability]
        return results

    @staticmethod
    def _phase8_alert(alert: dict[str, Any]) -> dict[str, Any]:
        return {**alert, "alert_type": "TRAJECTORY_ANOMALY", "alert_source": "PHASE8"}

    @staticmethod
    def _puc_alert(alert: dict[str, Any]) -> dict[str, Any]:
        return {**alert, "alert_source": "PUC", "trajectory_id": None, "event_ids": []}


def build_local_demo_service() -> tuple[Phase9Service, tempfile.TemporaryDirectory[str]]:
    """Create a local-only fixture service; caller owns the temporary directory."""
    directory = tempfile.TemporaryDirectory()
    pipeline = step_231.run_step_2_30_pipeline()
    repository = Phase7TrajectoryRepository(Path(directory.name) / "phase9_demo_store.json")
    repository.bootstrap(pipeline["identity_records"], pipeline["filtered_events"])
    service = Phase9Service(repository)
    service.refresh()
    return service, directory
