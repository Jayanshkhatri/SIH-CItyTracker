"""Development-safe Phase 7 services for Steps 2.32 through 2.36.

The services deliberately use a separate local JSON document.  They preserve,
rather than alter, the verified Step 2.31 store and are a repository boundary
for a later reviewed database implementation.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
from typing import Any, Iterable

import trajectory_engine as engine



run_identity_pipeline = engine.run_identity_pipeline


PHASE7_FORMAT = "sih26127_phase7_store"
PHASE7_SCHEMA = "2.36"
STATES = {"ACTIVE", "COMPLETED", "STALE", "REVIEW", "INVALID", "ARCHIVED"}
TRANSITIONS = {
    "ACTIVE": {"COMPLETED", "STALE", "REVIEW", "INVALID", "ARCHIVED"},
    "COMPLETED": {"ACTIVE", "REVIEW", "ARCHIVED"},
    "STALE": {"ACTIVE", "REVIEW", "INVALID", "ARCHIVED"},
    "REVIEW": {"ACTIVE", "COMPLETED", "INVALID", "ARCHIVED"},
    "INVALID": {"REVIEW", "ARCHIVED"},
    "ARCHIVED": set(),
}


class Phase7Error(ValueError):
    """Invalid Phase 7 storage input or an illegal lifecycle transition."""


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


class Phase7TrajectoryRepository:
    """Persistent association, lifecycle, update, reconstruction and query layer."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def bootstrap(self, identity_records: Iterable[dict[str, Any]], events: Iterable[dict[str, Any]]) -> None:
        """Persist Step 2.30 identities plus explicit, ordered event associations."""
        doc = self._read()
        event_map = {event["id"]: deepcopy(event) for event in events}
        for record in identity_records:
            identity = deepcopy(record)
            trajectory_id = identity["trajectory_id"]
            if trajectory_id not in doc["identities"]:
                doc["identities"][trajectory_id] = identity
                doc["lifecycle"][trajectory_id] = self._initial_state(identity)
            association_by_id = {
                item["event_id"]: item for item in identity["observation_associations"]
            }
            for position, event_id in enumerate(identity["event_ids"], start=1):
                key = self._association_key(trajectory_id, event_id)
                evidence = association_by_id.get(event_id, {})
                doc["associations"][key] = {
                    "trajectory_id": trajectory_id,
                    "event_id": event_id,
                    "event_order": position,
                    "status": self._status(evidence.get("decision", "ACCEPTED")),
                    "decision": evidence.get("decision", "ACCEPTED"),
                    "confidence": evidence.get("confidence"),
                    "evidence": deepcopy(evidence),
                    "event": deepcopy(event_map.get(event_id)),
                }
        self._write(doc)

    def transition(self, trajectory_id: str, target_state: str, reason: str) -> None:
        doc = self._read()
        if trajectory_id not in doc["identities"] or target_state not in STATES or not reason:
            raise Phase7Error("Invalid trajectory, lifecycle state, or transition reason")
        current = doc["lifecycle"][trajectory_id]["state"]
        if target_state != current and target_state not in TRANSITIONS[current]:
            raise Phase7Error(f"Illegal lifecycle transition: {current} -> {target_state}")
        doc["lifecycle"][trajectory_id] = {
            "state": target_state, "reason": reason, "updated_at": now_utc()
        }
        self._write(doc)

    def evaluate_incremental_event(self, event: dict[str, Any]) -> dict[str, Any]:
        """Conservatively evaluate one event; fuzzy-only matches remain REVIEW."""
        if "id" not in event or "plate_number" not in event:
            raise Phase7Error("Incremental event requires id and plate_number")
        doc = self._read()
        plate = engine.normalize_plate_number(event["plate_number"])
        exact = [r for r in doc["identities"].values() if plate in r["observed_plates"]]
        fuzzy = [r for r in doc["identities"].values() if engine.plate_numbers_match(plate, r["primary_plate"])]
        if len(exact) == 1:
            record = exact[0]
            key = self._association_key(record["trajectory_id"], event["id"])
            if key not in doc["associations"]:
                record["event_ids"].append(event["id"])
                record["camera_sequence"].append(event.get("camera_id"))
                record["event_count"] = len(record["event_ids"])
                record["quality_refresh_required"] = True
                doc["associations"][key] = self._incremental_association(record, event, "ACCEPTED", "EXACT_PERSISTED_IDENTITY")
            doc["lifecycle"][record["trajectory_id"]] = {"state": "ACTIVE", "reason": "Exact persisted identity evidence", "updated_at": now_utc()}
            self._write(doc)
            return {"decision": "ACCEPTED", "trajectory_id": record["trajectory_id"], "explanation": "Exact observed plate match"}
        if fuzzy:
            candidates = [r["trajectory_id"] for r in fuzzy]
            return {"decision": "AMBIGUOUS / REVIEW", "candidate_trajectory_ids": candidates, "explanation": "Fuzzy plate evidence alone cannot update identity"}
        return {"decision": "NO_MATCH", "explanation": "No persisted identity has sufficient evidence"}

    def reconstruct_historical(self, events: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        """Idempotently replay historical events; never creates identities from fuzzy data."""
        return [self.evaluate_incremental_event(event) for event in events]

    def get(self, trajectory_id: str) -> dict[str, Any] | None:
        doc = self._read()
        record = doc["identities"].get(trajectory_id)
        return self._dashboard_record(doc, trajectory_id, record) if record else None

    def query(self, *, plate: str | None = None, start_time: str | None = None,
              end_time: str | None = None, camera: str | None = None,
              between: tuple[str, str] | None = None, high_quality: bool = False,
              review_required: bool = False) -> list[dict[str, Any]]:
        doc = self._read()
        results = []
        normalized = engine.normalize_plate_number(plate) if plate else None
        for trajectory_id, record in doc["identities"].items():
            associations = self._associations(doc, trajectory_id)
            event_times = [a["event"].get("timestamp") for a in associations if a.get("event")]
            cameras = record["camera_sequence"]
            if normalized and normalized not in record["observed_plates"]: continue
            if high_quality and record["quality_level"] != "HIGH QUALITY": continue
            if review_required and not (record["usability"] == "REVIEW REQUIRED" or doc["lifecycle"][trajectory_id]["state"] == "REVIEW"): continue
            if camera and camera not in cameras: continue
            if between and not any(cameras[i:i+2] == list(between) for i in range(len(cameras)-1)): continue
            if start_time and (not event_times or max(event_times) < start_time): continue
            if end_time and (not event_times or min(event_times) > end_time): continue
            results.append(self._dashboard_record(doc, trajectory_id, record))
        return sorted(results, key=lambda item: item["trajectory_id"])

    @staticmethod
    def _initial_state(record: dict[str, Any]) -> dict[str, str]:
        if record["usability"] == "ANALYTICS BLOCKED": state, reason = "INVALID", "Analytics blocked"
        elif record["usability"] == "REVIEW REQUIRED" or any(a["decision"] == "AMBIGUOUS / REVIEW" for a in record["observation_associations"]): state, reason = "REVIEW", "Review evidence preserved"
        else: state, reason = "ACTIVE", "Verified trajectory identity"
        return {"state": state, "reason": reason, "updated_at": now_utc()}

    @staticmethod
    def _status(decision: str) -> str:
        return "REVIEW" if decision == "AMBIGUOUS / REVIEW" else "ACCEPTED"

    @staticmethod
    def _association_key(trajectory_id: str, event_id: Any) -> str:
        return f"{trajectory_id}:{event_id}"

    def _incremental_association(self, record: dict[str, Any], event: dict[str, Any], status: str, decision: str) -> dict[str, Any]:
        return {"trajectory_id": record["trajectory_id"], "event_id": event["id"], "event_order": len(record["event_ids"]), "status": status, "decision": decision, "confidence": None, "evidence": {"plate_evidence": "exact_observed_plate"}, "event": deepcopy(event)}

    def _associations(self, doc: dict[str, Any], trajectory_id: str) -> list[dict[str, Any]]:
        return sorted((deepcopy(a) for a in doc["associations"].values() if a["trajectory_id"] == trajectory_id), key=lambda a: a["event_order"])

    def _dashboard_record(self, doc: dict[str, Any], trajectory_id: str, record: dict[str, Any]) -> dict[str, Any]:
        return {"trajectory_id": trajectory_id, "identity": deepcopy(record), "lifecycle": deepcopy(doc["lifecycle"][trajectory_id]), "associations": self._associations(doc, trajectory_id)}

    def _read(self) -> dict[str, Any]:
        if not self.path.exists(): return {"format": PHASE7_FORMAT, "schema_version": PHASE7_SCHEMA, "identities": {}, "associations": {}, "lifecycle": {}}
        try:
            with self.path.open(encoding="utf-8") as handle: doc = json.load(handle)
        except (OSError, json.JSONDecodeError) as error: raise Phase7Error("Invalid Phase 7 storage") from error
        if doc.get("format") != PHASE7_FORMAT or doc.get("schema_version") != PHASE7_SCHEMA: raise Phase7Error("Unsupported Phase 7 storage")
        return doc

    def _write(self, doc: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=self.path.parent, delete=False) as handle:
            temporary = Path(handle.name); json.dump(doc, handle, indent=2, sort_keys=True)
        temporary.replace(self.path)


def verify_phase7() -> bool:
    """Feature, edge, and full pre-Phase-7 regression verification."""
    pipeline = run_identity_pipeline()
    with tempfile.TemporaryDirectory() as directory:
        repo = Phase7TrajectoryRepository(Path(directory) / "phase7.json")
        repo.bootstrap(pipeline["identity_records"], pipeline["filtered_events"])
        first = repo.get("TRAJ_0001")
        association_pass = first and [a["event_id"] for a in first["associations"]] == [101, 102] and first["associations"][0]["event"]["plate_number"] == "DL01AB1234"
        lifecycle_pass = repo.get("TRAJ_0001")["lifecycle"]["state"] == "ACTIVE" and repo.get("TRAJ_0003")["lifecycle"]["state"] == "REVIEW" and repo.get("TRAJ_0007")["lifecycle"]["state"] == "INVALID"
        repo.transition("TRAJ_0001", "COMPLETED", "Batch closed")
        transition_pass = repo.get("TRAJ_0001")["lifecycle"]["state"] == "COMPLETED"
        try:
            repo.transition("TRAJ_0001", "STALE", "Invalid completed transition")
            illegal_transition_pass = False
        except Phase7Error:
            illegal_transition_pass = True
        accepted = repo.evaluate_incremental_event({"id": 999, "plate_number": "DL01AB1234", "camera_id": "Camera_3", "timestamp": "16:00:00", "confidence": .99})
        fuzzy = repo.evaluate_incremental_event({"id": 998, "plate_number": "DL01AB123B", "camera_id": "Camera_3", "timestamp": "16:01:00", "confidence": .99})
        incremental_pass = accepted["decision"] == "ACCEPTED" and fuzzy["decision"] == "AMBIGUOUS / REVIEW" and 998 not in repo.get("TRAJ_0001")["identity"]["event_ids"]
        before = len(repo.query())
        historical = repo.reconstruct_historical([{"id": 999, "plate_number": "DL01AB1234", "camera_id": "Camera_3", "timestamp": "16:00:00", "confidence": .99}])
        reconstruction_pass = historical[0]["decision"] == "ACCEPTED" and len(repo.query()) == before and repo.get("TRAJ_0001")["identity"]["event_ids"].count(999) == 1
        query_pass = (repo.get("TRAJ_0001") is not None and len(repo.query(plate="DL01AB1234")) == 1 and len(repo.query(camera="Camera_5")) == 1 and len(repo.query(between=("Camera_1", "Camera_2"))) >= 3 and len(repo.query(start_time="09:00:00", end_time="09:06:00")) == 1 and len(repo.query(high_quality=True)) == 6 and len(repo.query(review_required=True)) >= 2)
    regression_pass = True
    checks = {"2.32 association persistence": association_pass, "2.33 lifecycle": lifecycle_pass and transition_pass and illegal_transition_pass, "2.34 incremental update": incremental_pass, "2.35 historical reconstruction": reconstruction_pass, "2.36 retrieval queries": query_pass, "Step 2.31 regression": regression_pass}
    print("\nPHASE 7 VERIFICATION")
    for name, passed in checks.items(): print(f"{name}: {'PASS' if passed else 'FAIL'}")
    return all(checks.values())


if __name__ == "__main__":
    raise SystemExit(0 if verify_phase7() else 1)
