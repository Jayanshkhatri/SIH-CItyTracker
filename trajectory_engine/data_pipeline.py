"""Database-to-engine orchestration using verified algorithm functions.

The pipeline persists trajectories only to an explicitly supplied local Phase 7
repository.  It may create a ``PUC_UNVERIFIED`` alert through the supplied PUC
repository; that is its sole Supabase write.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import date
from typing import Any, Iterable

import trajectory_engine as engine
from supabase_repository import SupabaseEventReader, SupabasePucRepository
from logging_utils import logger, timed
from puc_verification import PucVerificationResult, verify_puc
from trajectory_repository import Phase7TrajectoryRepository


def normalize_source_events(rows: Iterable[dict[str, Any]], camera_id_map: dict[str, str] | None = None) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Validate/adapt source rows without inventing missing camera or time data."""
    output, rejected, seen = [], 0, set()
    for row in rows:
        try:
            event_id, plate, timestamp = row["id"], row["plate_number"], row["timestamp"]
            raw_camera = str(row["camera_id"])
            camera = (camera_id_map or {}).get(raw_camera, row.get("camera_name") or raw_camera)
            if not event_id or not plate or not timestamp or not camera or event_id in seen:
                raise ValueError("missing or duplicate required event field")
            engine.parse_time(timestamp)
            output.append({"id": event_id, "plate_number": plate, "camera_id": camera,
                           "timestamp": timestamp, "event_timestamp": row.get("event_timestamp"),
                           "event_date": row.get("event_date"), "confidence": float(row["confidence"])})
            seen.add(event_id)
        except (KeyError, TypeError, ValueError):
            rejected += 1
    return output, {"input_count": len(output) + rejected, "accepted_count": len(output), "rejected_count": rejected}


class ReadOnlyDatabasePipeline:
    """Fetches production rows safely; PUC alert sync is separately explicit."""
    def __init__(self, reader: SupabaseEventReader, repository: Phase7TrajectoryRepository,
                 camera_id_map: dict[str, str], puc_repository: SupabasePucRepository | None = None) -> None:
        self.reader, self.repository, self.camera_id_map = reader, repository, camera_id_map
        self.puc_repository = puc_repository

    def fetch_and_normalize(self, *, limit: int = 1000, offset: int = 0) -> tuple[list[dict[str, Any]], dict[str, int]]:
        with timed("pipeline_fetch_and_normalize", limit=limit, offset=offset):
            events, stats = normalize_source_events(self.reader.fetch_events(limit=limit, offset=offset), self.camera_id_map)
        logger.info("pipeline_source_normalized accepted=%s rejected=%s", stats["accepted_count"], stats["rejected_count"])
        return events, stats

    def reconstruct_to_local_repository(
        self,
        events: Iterable[dict[str, Any]],
        *,
        network: Any | None = None,
    ) -> dict[str, Any]:
        """Run the verified core stages and persist only to the local repository.

        This is orchestration, not a second trajectory algorithm. Production
        callers supply a reviewed camera map/network and retain control over the
        local repository path; source database rows are never changed.
        """
        source = list(events)
        with _legacy_engine_network(network):
            with timed("pipeline_reconstruct", source_events=len(source)):
                filtered, low_confidence_removed = engine.filter_low_confidence_events(source)
                filtered, duplicate_removed = engine.remove_same_camera_duplicates(filtered)
                trajectories = engine.build_trajectories(filtered)
                fuzzy_matches = engine.find_fuzzy_plate_matches(filtered)
                observations, seen = [], set()
                for match in fuzzy_matches:
                    for event in (match["event_a"], match["event_b"]):
                        if event["id"] not in seen:
                            observations.append(event); seen.add(event["id"])
                associations = engine.run_trajectory_level_association(observations, trajectories)
                consistency = engine.apply_consistency_validation(associations, trajectories)
                confidence = engine.apply_confidence_aggregation(consistency, trajectories)
                confidence = engine.apply_step_2_26_validation(confidence, trajectories)
                continuity = engine.run_trajectory_continuity_validation(trajectories)
                quality = engine.run_trajectory_quality_scoring(trajectories, continuity)
                usability = engine.run_trajectory_usability_classification(quality)
                identities = engine.build_trajectory_identity_records(trajectories, quality, usability, confidence)
                self.repository.bootstrap(identities, filtered)
        result = {"source_event_count": len(source), "accepted_event_count": len(filtered),
                  "low_confidence_removed": len(low_confidence_removed), "duplicate_removed": len(duplicate_removed),
                  "trajectory_count": len(identities), "persistence_target": "LOCAL_PHASE7_REPOSITORY_ONLY"}
        logger.info("pipeline_reconstruction_completed trajectories=%s accepted_events=%s", result["trajectory_count"], result["accepted_event_count"])
        return result

    def synchronize_puc_alerts(self) -> dict[str, Any]:
        """Check every stored usable primary plate using the latest vehicle event date."""
        if self.puc_repository is None:
            raise ValueError("PUC repository is required for PUC synchronization")
        results: list[PucVerificationResult] = []
        alerts_created = 0
        for record in self.repository.query():
            plate = record["identity"].get("primary_plate")
            reference = self._latest_event_date(record)
            if not plate or reference is None:
                continue
            result = verify_puc(plate, reference, self.puc_repository.fetch_records(plate))
            _, created = self.puc_repository.create_alert_if_absent(result)
            results.append(result)
            alerts_created += int(created)
        logger.info("pipeline_puc_sync_completed checked=%s alerts_created=%s", len(results), alerts_created)
        return {"checked_count": len(results), "alerts_created": alerts_created, "results": results}

    @staticmethod
    def _latest_event_date(record: dict[str, Any]) -> date | None:
        values = []
        for association in record.get("associations", []):
            event = association.get("event") or {}
            raw = event.get("event_date") or event.get("event_timestamp")
            if raw:
                try:
                    values.append(date.fromisoformat(str(raw)[:10]))
                except ValueError:
                    continue
        return max(values) if values else None


@contextmanager
def _legacy_engine_network(network: Any | None):
    """Temporarily adapt the verified legacy checks to an explicit network.

    The legacy engine exposes camera data and graph adjacency as module globals.
    This narrow compatibility boundary lets its existing connectivity validation
    operate on the runtime's actual camera IDs and directed connections without
    changing the verified algorithm or weakening any checks.
    """
    if network is None:
        yield
        return

    cameras = getattr(network, "cameras", None)
    outgoing = getattr(network, "_outgoing", None)
    if not isinstance(cameras, dict) or not isinstance(outgoing, dict):
        raise ValueError("Trajectory network must expose cameras and directed connections")

    graph = {
        camera_id: [
            connection.destination_camera
            for connection in connections
            if connection.enabled
        ]
        for camera_id, connections in outgoing.items()
    }
    if set(graph) != set(cameras):
        raise ValueError("Trajectory network graph must include every configured camera")

    original_cameras, original_graph = engine.CAMERAS, engine.CAMERA_GRAPH
    engine.CAMERAS, engine.CAMERA_GRAPH = cameras, graph
    try:
        yield
    finally:
        engine.CAMERAS, engine.CAMERA_GRAPH = original_cameras, original_graph


def run_real_data_batch(*, connection_factory, repository: Phase7TrajectoryRepository,
                        camera_id_map: dict[str, str], limit: int = 1000,
                        offset: int = 0) -> dict[str, Any]:
    """Explicit batch entry point; local demo/API defaults never invoke it.

    It reads source rows and may insert only required PUC_UNVERIFIED alerts.
    """
    reader = SupabaseEventReader(connection_factory)
    puc_repository = SupabasePucRepository(connection_factory)
    pipeline = ReadOnlyDatabasePipeline(reader, repository, camera_id_map, puc_repository)
    events, source_stats = pipeline.fetch_and_normalize(limit=limit, offset=offset)
    reconstruction = pipeline.reconstruct_to_local_repository(events)
    puc_sync = pipeline.synchronize_puc_alerts()
    return {"source": source_stats, "reconstruction": reconstruction, "puc": puc_sync}
