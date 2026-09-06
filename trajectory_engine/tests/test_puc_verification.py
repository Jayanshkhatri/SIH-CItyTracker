"""Credential-free verification for the pre-Phase-10 PUC integration."""
from __future__ import annotations

import asyncio
from datetime import date
import unittest

import httpx

from api import create_app
from supabase_repository import DataAccessError, SupabasePucRepository
from data_pipeline import ReadOnlyDatabasePipeline
from trajectory_service import build_local_demo_service
from puc_verification import PUC_ALERT_TYPE, verify_puc


class PucPolicyTests(unittest.TestCase):
    def test_valid_expired_and_boundary_dates(self) -> None:
        valid = {"id": 1, "plate_number": "DL 01-AB 1234", "puc_expiry_date": "2025-01-10", "status": " valid "}
        self.assertEqual(verify_puc("dl01ab1234", "2025-01-10", [valid]).outcome, "VALID")
        self.assertEqual(verify_puc("DL01AB1234", "2025-01-09", [valid]).outcome, "VALID")
        expired = verify_puc("DL01AB1234", "2025-01-11", [valid])
        self.assertEqual((expired.outcome, expired.severity), ("EXPIRED", "HIGH"))

    def test_not_found_invalid_status_and_missing_expiry(self) -> None:
        self.assertEqual(verify_puc("DL01AB1234", "2025-01-01", []).outcome, "RECORD_NOT_FOUND")
        invalid = verify_puc("DL01AB1234", "2025-01-01", [{"id": 1, "plate_number": "DL01AB1234", "puc_expiry_date": "2025-12-01", "status": " suspended "}])
        missing = verify_puc("DL01AB1234", "2025-01-01", [{"id": 1, "plate_number": "DL01AB1234", "puc_expiry_date": None, "status": "VALID"}])
        self.assertEqual((invalid.outcome, invalid.severity), ("INVALID_STATUS", "HIGH"))
        self.assertEqual((missing.outcome, missing.severity), ("MISSING_EXPIRY", "HIGH"))

    def test_multiple_records_use_latest_non_null_then_highest_id(self) -> None:
        records = [
            {"id": 9, "plate_number": "DL01AB1234", "puc_expiry_date": None, "status": "VALID"},
            {"id": 1, "plate_number": "DL01AB1234", "puc_expiry_date": "2025-04-01", "status": "VALID"},
            {"id": 2, "plate_number": "DL 01 AB 1234", "puc_expiry_date": "2025-05-01", "status": "VALID"},
        ]
        self.assertEqual(verify_puc("DL01AB1234", "2025-01-01", records).record_id, 2)
        tied = [dict(records[1], id=3), dict(records[1], id=4)]
        self.assertEqual(verify_puc("DL01AB1234", "2025-01-01", tied).record_id, 4)
        nulls = [dict(records[0], id=5), dict(records[0], id=6)]
        self.assertEqual(verify_puc("DL01AB1234", "2025-01-01", nulls).record_id, 6)


class _MemoryPucRepository:
    def __init__(self, records: dict[str, list[dict]]) -> None:
        self.records, self.verified, self.created = records, [], []

    def fetch_records(self, plate: str) -> list[dict]:
        return self.records.get(plate, [])

    def create_alert_if_absent(self, result):
        self.verified.append(result)
        if not result.alert_required:
            return None, False
        self.created.append(result)
        return {"alert_id": len(self.created)}, True


class _RecordRepository:
    def __init__(self, records: list[dict]) -> None: self.records = records
    def query(self): return self.records


def _record(plate: str | None, event_date: str | None, state: str) -> dict:
    event = {} if event_date is None else {"event_date": event_date}
    return {"identity": {"primary_plate": plate}, "lifecycle": {"state": state}, "associations": [{"event": event}]}


class PipelinePucTests(unittest.TestCase):
    def test_every_trajectory_state_is_checked_using_historical_event_date(self) -> None:
        records = [_record("NORMAL1", "2024-01-02", "ACTIVE"), _record("REVIEW1", "2024-01-03", "REVIEW"),
                   _record("ANOMALY1", "2024-01-04", "ACTIVE"), _record("INVALID1", "2024-01-05", "INVALID"),
                   _record(None, "2024-01-06", "ACTIVE"), _record("NODATE1", None, "ACTIVE")]
        valid = {"id": 1, "plate_number": "NORMAL1", "puc_expiry_date": "2024-12-31", "status": "VALID"}
        puc = _MemoryPucRepository({"NORMAL1": [valid]})
        pipeline = ReadOnlyDatabasePipeline(None, _RecordRepository(records), {}, puc)
        result = pipeline.synchronize_puc_alerts()
        self.assertEqual(result["checked_count"], 4)
        self.assertEqual([item.reference_date for item in puc.verified], [date(2024, 1, day) for day in range(2, 6)])
        self.assertEqual(len(puc.created), 3)


class _Cursor:
    def __init__(self, connection): self.connection = connection
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def execute(self, query, parameters):
        self.connection.queries.append(query)
        if "INSERT" in query and self.connection.fail_insert: raise RuntimeError("insert failure")
        self.connection.last_query = query
    def fetchall(self): return self.connection.rows
    def fetchone(self):
        if "SELECT" in self.connection.last_query: return self.connection.existing
        return (77, "DL01AB1234", PUC_ALERT_TYPE, "HIGH", "issue", False)


class _Connection:
    def __init__(self, *, existing=None, fail_insert=False, rows=None):
        self.existing, self.fail_insert, self.rows = existing, fail_insert, rows or []
        self.queries, self.last_query, self.committed, self.rolled_back, self.closed = [], "", False, False, False
    def cursor(self): return _Cursor(self)
    def commit(self): self.committed = True
    def rollback(self): self.rolled_back = True
    def close(self): self.closed = True


class AlertRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.issue = verify_puc("DL01AB1234", "2025-01-01", [])

    def test_explicit_row_mapper_and_alert_lifecycle_rules(self) -> None:
        mapped_connection = _Connection(rows=[(5, "DL01AB1234", PUC_ALERT_TYPE, "MEDIUM", "x", False)])
        repo = SupabasePucRepository(lambda: mapped_connection)
        rows = repo._fetch_rows("SELECT deliberately_not_named_like_a_table", [], "test_mapper", repo._row_to_alert)
        self.assertEqual(rows[0]["alert_id"], 5)

        duplicate_connection = _Connection(existing=(2, "DL01AB1234", PUC_ALERT_TYPE, "HIGH", "old", False))
        duplicate = SupabasePucRepository(lambda: duplicate_connection).create_alert_if_absent(self.issue)
        self.assertFalse(duplicate[1])
        self.assertFalse(any("INSERT" in query for query in duplicate_connection.queries))

        resolved_old_connection = _Connection(existing=None)
        created = SupabasePucRepository(lambda: resolved_old_connection).create_alert_if_absent(self.issue)
        self.assertTrue(created[1])
        self.assertTrue(resolved_old_connection.committed)
        self.assertFalse(any("UPDATE" in query for query in resolved_old_connection.queries))
        self.assertTrue(any("is_resolved = FALSE" in query for query in resolved_old_connection.queries))

    def test_failed_insert_rolls_back_and_closes_connection(self) -> None:
        connection = _Connection(fail_insert=True)
        with self.assertRaises(DataAccessError):
            SupabasePucRepository(lambda: connection).create_alert_if_absent(self.issue)
        self.assertTrue(connection.rolled_back)
        self.assertTrue(connection.closed)
        self.assertFalse(connection.committed)


class _ReadOnlyPucRepository:
    def __init__(self): self.write_attempts = 0; self.reads = 0
    def list_puc_alerts(self):
        self.reads += 1
        return [{"alert_id": 9, "plate_number": "DL01AB1234", "alert_type": PUC_ALERT_TYPE,
                 "severity": "HIGH", "message": "PUC issue", "is_resolved": False}]
    def create_alert_if_absent(self, result):
        self.write_attempts += 1
        raise AssertionError("GET must never synchronize PUC alerts")


class ApiPucTests(unittest.TestCase):
    def test_alert_filters_are_safe_and_get_is_read_only(self) -> None:
        service, directory = build_local_demo_service()
        try:
            puc = _ReadOnlyPucRepository(); service.puc_repository = puc; service.refresh()
            app = create_app(service)
            async def call():
                transport = httpx.ASGITransport(app=app)
                async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                    return await client.get("/v1/alerts", params={"severity": "HIGH", "alert_type": PUC_ALERT_TYPE}), await client.get("/v1/trajectories/TRAJ_0001")
            alerts, trajectory = asyncio.run(call())
            payload = alerts.json()["items"]
            self.assertEqual(alerts.status_code, 200)
            self.assertEqual(payload, [{"alert_source": "PUC", "alert_id": 9, "plate_number": "DL01AB1234", "alert_type": PUC_ALERT_TYPE, "severity": "HIGH", "message": "PUC issue", "is_resolved": False}])
            self.assertEqual(trajectory.status_code, 200)
            self.assertEqual(puc.write_attempts, 0)
        finally:
            directory.cleanup()


if __name__ == "__main__":
    unittest.main()
