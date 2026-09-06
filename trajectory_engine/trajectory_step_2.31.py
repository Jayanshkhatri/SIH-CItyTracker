"""SIH26127 Step 2.31 — trajectory persistence / storage layer.

This module extends the verified Step 2.30 identity records without changing
the trajectory engine baseline. It uses an explicit JSON repository for
development. A future database repository can implement the same operations
after the Supabase schema has been designed and reviewed.

Step 2.31 stores the Step 2.30 event references and association snapshots as
trajectory metadata. It does not decide or alter associations; the normalized,
evidence-bearing identity-to-event association model remains Step 2.32 scope.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
from typing import Any, Callable, Iterable

import trajectory as step_2_30


STORAGE_SCHEMA_VERSION = "2.31"
STORAGE_FORMAT = "sih26127_trajectory_store"
IDENTITY_STATUS_PERSISTED = "PERSISTED"

REQUIRED_STEP_2_30_FIELDS = {
    "trajectory_id",
    "primary_plate",
    "observed_plates",
    "event_ids",
    "observation_associations",
    "camera_sequence",
    "event_count",
    "quality_score",
    "quality_level",
    "usability",
}


def utc_now() -> str:
    """Return an ISO-8601 UTC timestamp suitable for persisted metadata."""
    return datetime.now(timezone.utc).isoformat()


class TrajectoryStorageError(ValueError):
    """Raised when a persistence document or identity record is invalid."""


class JsonTrajectoryStore:
    """Durable, deterministic storage for Step 2.30 trajectory identities.

    The document is keyed by ``trajectory_id``. Saving an existing identity is
    an explicit metadata refresh, not a merge: no records are inferred, joined,
    or removed. Files are written to a temporary sibling and atomically
    replaced only after the complete JSON document has been serialized.
    """

    def __init__(
        self,
        storage_path: str | Path,
        clock: Callable[[], str] = utc_now,
    ) -> None:
        self.storage_path = Path(storage_path)
        self._clock = clock

    def save_records(
        self,
        identity_records: Iterable[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Persist Step 2.30 records and return their stored representations."""
        records = [deepcopy(record) for record in identity_records]
        self._validate_unique_input_ids(records)

        document = self._read_document()
        stored_records = document["records"]
        now = self._clock()

        for record in records:
            self._validate_identity_record(record)
            trajectory_id = record["trajectory_id"]
            existing = stored_records.get(trajectory_id)
            created_at = existing["created_at"] if existing else now
            stored_records[trajectory_id] = self._make_stored_record(
                record,
                created_at=created_at,
                updated_at=now,
            )

        self._write_document(document)
        return [
            deepcopy(stored_records[record["trajectory_id"]])
            for record in records
        ]

    def get_record(self, trajectory_id: str) -> dict[str, Any] | None:
        """Retrieve one persisted trajectory identity, or ``None`` if absent."""
        if not isinstance(trajectory_id, str) or not trajectory_id.strip():
            raise TrajectoryStorageError("trajectory_id must be a non-empty string")

        record = self._read_document()["records"].get(trajectory_id)
        return deepcopy(record) if record is not None else None

    def list_records(self) -> list[dict[str, Any]]:
        """Retrieve all records in deterministic trajectory-ID order."""
        records = self._read_document()["records"]
        return [deepcopy(records[key]) for key in sorted(records)]

    def _read_document(self) -> dict[str, Any]:
        if not self.storage_path.exists():
            return self._empty_document()

        try:
            with self.storage_path.open("r", encoding="utf-8") as handle:
                document = json.load(handle)
        except (OSError, json.JSONDecodeError) as error:
            raise TrajectoryStorageError(
                f"Unable to read trajectory storage: {self.storage_path}"
            ) from error

        self._validate_document(document)
        return document

    def _write_document(self, document: dict[str, Any]) -> None:
        self._validate_document(document)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.storage_path.parent,
                prefix=f".{self.storage_path.name}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                temporary_path = Path(handle.name)
                json.dump(document, handle, indent=2, sort_keys=True)
                handle.write("\n")

            temporary_path.replace(self.storage_path)
        except OSError as error:
            raise TrajectoryStorageError(
                f"Unable to write trajectory storage: {self.storage_path}"
            ) from error
        finally:
            if temporary_path is not None and temporary_path.exists():
                temporary_path.unlink()

    @staticmethod
    def _empty_document() -> dict[str, Any]:
        return {
            "format": STORAGE_FORMAT,
            "schema_version": STORAGE_SCHEMA_VERSION,
            "records": {},
        }

    @staticmethod
    def _validate_unique_input_ids(records: list[dict[str, Any]]) -> None:
        ids = [record.get("trajectory_id") for record in records]
        if len(ids) != len(set(ids)):
            raise TrajectoryStorageError(
                "Input contains duplicate trajectory_id values; records were not saved"
            )

    @staticmethod
    def _validate_identity_record(record: dict[str, Any]) -> None:
        if not isinstance(record, dict):
            raise TrajectoryStorageError("Each trajectory identity must be a dictionary")

        missing = REQUIRED_STEP_2_30_FIELDS - set(record)
        if missing:
            raise TrajectoryStorageError(
                "Step 2.30 identity record is missing fields: "
                + ", ".join(sorted(missing))
            )

        if not isinstance(record["trajectory_id"], str) or not record["trajectory_id"]:
            raise TrajectoryStorageError("trajectory_id must be a non-empty string")
        if not isinstance(record["event_ids"], list):
            raise TrajectoryStorageError("event_ids must be a list")
        if not isinstance(record["observation_associations"], list):
            raise TrajectoryStorageError("observation_associations must be a list")
        if record["event_count"] != len(record["event_ids"]):
            raise TrajectoryStorageError("event_count must match the number of event_ids")

    @staticmethod
    def _validate_document(document: Any) -> None:
        if not isinstance(document, dict):
            raise TrajectoryStorageError("Trajectory storage document must be an object")
        if document.get("format") != STORAGE_FORMAT:
            raise TrajectoryStorageError("Unsupported trajectory storage format")
        if document.get("schema_version") != STORAGE_SCHEMA_VERSION:
            raise TrajectoryStorageError("Unsupported trajectory storage schema version")
        if not isinstance(document.get("records"), dict):
            raise TrajectoryStorageError("Trajectory storage records must be an object")

        for trajectory_id, record in document["records"].items():
            JsonTrajectoryStore._validate_identity_record(record)
            if record["trajectory_id"] != trajectory_id:
                raise TrajectoryStorageError("Record key does not match trajectory_id")
            if record.get("identity_status") != IDENTITY_STATUS_PERSISTED:
                raise TrajectoryStorageError("Stored record has an invalid identity status")
            if not record.get("created_at") or not record.get("updated_at"):
                raise TrajectoryStorageError("Stored record is missing persistence timestamps")

    @staticmethod
    def _make_stored_record(
        identity_record: dict[str, Any],
        created_at: str,
        updated_at: str,
    ) -> dict[str, Any]:
        stored = deepcopy(identity_record)
        stored["identity_status"] = IDENTITY_STATUS_PERSISTED
        stored["identity_source"] = "STEP_2.30"
        stored["created_at"] = created_at
        stored["updated_at"] = updated_at
        return stored


def run_step_2_30_pipeline() -> dict[str, Any]:
    """Run the verified pipeline through identity creation without altering it."""
    filtered_events, low_confidence_removed = (
        step_2_30.filter_low_confidence_events(step_2_30.EVENTS)
    )
    filtered_events, duplicate_removed = (
        step_2_30.remove_same_camera_duplicates(filtered_events)
    )
    trajectories = step_2_30.build_trajectories(filtered_events)
    fuzzy_matches = step_2_30.find_fuzzy_plate_matches(filtered_events)
    validated_matches = step_2_30.validate_all_fuzzy_matches(fuzzy_matches)

    association_observations = []
    seen_event_ids = set()
    for match in fuzzy_matches:
        for event in (match["event_a"], match["event_b"]):
            if event["id"] not in seen_event_ids:
                association_observations.append(event)
                seen_event_ids.add(event["id"])

    association_results = step_2_30.run_trajectory_level_association(
        association_observations,
        trajectories,
    )
    consistency_results = step_2_30.apply_consistency_validation(
        association_results,
        trajectories,
    )
    confidence_results = step_2_30.apply_confidence_aggregation(
        consistency_results,
        trajectories,
    )
    confidence_results = step_2_30.apply_step_2_26_validation(
        confidence_results,
        trajectories,
    )
    continuity_results = step_2_30.run_trajectory_continuity_validation(trajectories)
    quality_results = step_2_30.run_trajectory_quality_scoring(
        trajectories,
        continuity_results,
    )
    usability_results = step_2_30.run_trajectory_usability_classification(
        quality_results
    )
    identity_records = step_2_30.build_trajectory_identity_records(
        trajectories,
        quality_results,
        usability_results,
        confidence_results,
    )

    return {
        "filtered_events": filtered_events,
        "low_confidence_removed": low_confidence_removed,
        "duplicate_removed": duplicate_removed,
        "trajectories": trajectories,
        "fuzzy_matches": fuzzy_matches,
        "validated_matches": validated_matches,
        "confidence_results": confidence_results,
        "quality_results": quality_results,
        "usability_results": usability_results,
        "identity_records": identity_records,
    }


def verify_step_2_31() -> bool:
    """Run normal, edge-case, and Step 2.30 regression verification."""
    pipeline = run_step_2_30_pipeline()
    records = pipeline["identity_records"]
    first_trajectory_id = records[0]["trajectory_id"]

    step_2_30_pass = step_2_30.verify_step_2_30(
        records,
        pipeline["trajectories"],
        pipeline["quality_results"],
        pipeline["usability_results"],
        pipeline["confidence_results"],
    )
    regression_pass = step_2_30.verify_regression_checks(
        filtered_events=pipeline["filtered_events"],
        duplicate_removed=pipeline["duplicate_removed"],
        trajectories=pipeline["trajectories"],
        fuzzy_matches=pipeline["fuzzy_matches"],
        validated_matches=pipeline["validated_matches"],
        suspicious_movements=step_2_30.find_suspicious_movements(
            pipeline["trajectories"]
        ),
        disconnected_routes=step_2_30.find_disconnected_routes(
            pipeline["trajectories"]
        ),
    )

    timestamps = iter(("2026-09-06T00:00:00+00:00", "2026-09-06T00:01:00+00:00"))
    with tempfile.TemporaryDirectory() as directory:
        storage_path = Path(directory) / "trajectory_store.json"
        store = JsonTrajectoryStore(storage_path, clock=lambda: next(timestamps))
        saved = store.save_records(records)
        retrieved = store.list_records()
        first_record = store.get_record(first_trajectory_id)
        ambiguous_record = next(
            record
            for record in retrieved
            if record["primary_plate"] == "DL02XY5678"
        )

        normal_pass = (
            storage_path.exists()
            and len(saved) == len(records) == 8
            and [record["trajectory_id"] for record in retrieved]
            == [record["trajectory_id"] for record in records]
            and first_record is not None
            and first_record["primary_plate"] == "DL01AB1234"
            and first_record["identity_status"] == IDENTITY_STATUS_PERSISTED
            and first_record["event_ids"] == [101, 102]
            and first_record["quality_score"] == 92.0
            and first_record["usability"] == "ANALYTICS READY"
            and first_record["created_at"] == "2026-09-06T00:00:00+00:00"
            and any(
                association["decision"] == "AMBIGUOUS / REVIEW"
                for association in ambiguous_record["observation_associations"]
            )
        )

        reloaded = JsonTrajectoryStore(storage_path).get_record(first_trajectory_id)
        reload_pass = reloaded == first_record
        no_merge_pass = len(retrieved) == len({r["trajectory_id"] for r in records})

        first_record["primary_plate"] = "MUTATED"
        defensive_copy_pass = (
            store.get_record(first_trajectory_id)["primary_plate"] == "DL01AB1234"
        )

        refreshed = store.save_records(records)[0]
        update_pass = (
            refreshed["created_at"] == "2026-09-06T00:00:00+00:00"
            and refreshed["updated_at"] == "2026-09-06T00:01:00+00:00"
        )

        missing_pass = store.get_record("TRAJ_999999") is None
        try:
            store.save_records([records[0], records[0]])
            duplicate_input_pass = False
        except TrajectoryStorageError:
            duplicate_input_pass = True

    print("\n" + "=" * 80)
    print("STEP 2.31 VERIFICATION")
    print("=" * 80)
    checks = {
        "Step 2.30 identity regression": step_2_30_pass,
        "Prior pipeline regression": regression_pass,
        "Persist and retrieve records": normal_pass,
        "Storage survives repository reload": reload_pass,
        "No automatic trajectory merging": no_merge_pass,
        "Returned records are defensive copies": defensive_copy_pass,
        "Update preserves creation timestamp": update_pass,
        "Missing identity returns None": missing_pass,
        "Duplicate input is rejected": duplicate_input_pass,
    }
    for label, passed in checks.items():
        print(f"{label}: {'PASS' if passed else 'FAIL'}")
    return all(checks.values())


def main() -> None:
    passed = verify_step_2_31()
    print("\n" + "=" * 80)
    print("STEP 2.31 FINAL STATUS")
    print("=" * 80)
    print(
        "Trajectory persistence / storage layer: "
        f"{'PASS' if passed else 'FAIL'}"
    )
    if passed:
        print("Step 2.31 verification checks passed.")
        print("No database schema or data was modified.")


if __name__ == "__main__":
    main()
