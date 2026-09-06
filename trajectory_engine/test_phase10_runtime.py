"""Credential-free verification for explicit Phase 10 runtime composition."""
from __future__ import annotations

import asyncio
from pathlib import Path
import tempfile
import unittest

import httpx

from phase10_runtime import Phase10Runtime, RuntimeConfig


class _Reader:
    def __init__(self, events=None):
        self.events = events if events is not None else [
            {"id": 1, "plate_number": "DL01AB1234", "camera_id": "1", "camera_name": "Camera_1",
             "timestamp": "09:00:00", "event_timestamp": "2025-01-01T09:00:00", "event_date": "2025-01-01", "confidence": .95},
            {"id": 2, "plate_number": "DL01AB1234", "camera_id": "1", "camera_name": "Camera_1",
             "timestamp": "09:05:00", "event_timestamp": "2025-01-01T09:05:00", "event_date": "2025-01-01", "confidence": .95},
        ]
        self.camera_limits, self.event_calls, self.fail = [], [], False

    def fetch_cameras(self, *, limit):
        self.camera_limits.append(limit)
        if self.fail: raise RuntimeError("reader unavailable")
        return [{"id": "1", "name": "Camera_1", "lat": 28.7041, "lon": 77.1025,
                 "coordinate_provenance": "SUPABASE"}]

    def fetch_events(self, *, limit, offset):
        self.event_calls.append((limit, offset))
        if self.fail: raise RuntimeError("reader unavailable")
        return self.events[offset:offset + limit]


class _PucRepository:
    def __init__(self, *, valid=True):
        self.valid, self.fetches, self.create_calls, self.list_calls, self.unresolved = valid, 0, 0, 0, set()

    def fetch_records(self, plate):
        self.fetches += 1
        return ([{"id": 1, "plate_number": plate, "puc_expiry_date": "2025-12-31", "status": "VALID"}]
                if self.valid else [])

    def create_alert_if_absent(self, result):
        self.create_calls += 1
        if not result.alert_required or result.normalized_plate in self.unresolved: return None, False
        self.unresolved.add(result.normalized_plate)
        return {"alert_id": len(self.unresolved)}, True

    def list_puc_alerts(self):
        self.list_calls += 1
        return []


class Phase10RuntimeTests(unittest.TestCase):
    def _runtime(self, directory, reader=None, puc=None, **config):
        return Phase10Runtime(RuntimeConfig(Path(directory) / "runtime.json", **config), lambda: None,
                              reader=reader or _Reader(), puc_repository=puc or _PucRepository())

    def test_composes_bounded_persistent_runtime_and_preserves_event_dates(self):
        with tempfile.TemporaryDirectory() as directory:
            reader, puc = _Reader(), _PucRepository()
            runtime = self._runtime(directory, reader, puc, camera_limit=1, event_limit=2, event_offset=0)
            result = runtime.refresh()
            self.assertTrue(result.succeeded)
            self.assertEqual(reader.camera_limits, [1])
            self.assertEqual(reader.event_calls, [(2, 0)])
            self.assertTrue((Path(directory) / "runtime.json").exists())
            record = runtime.service.repository.query()[0]
            self.assertEqual(record["associations"][0]["event"]["event_date"], "2025-01-01")
            self.assertEqual(runtime.status.public()["mode"], "REAL_SUPABASE")
            self.assertTrue(runtime.status.snapshot_ready)

    def test_explicit_refresh_runs_puc_and_second_refresh_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            puc = _PucRepository(valid=False); runtime = self._runtime(directory, puc=puc)
            first, second = runtime.refresh(), runtime.refresh()
            self.assertEqual((first.puc_checked_count, first.puc_alerts_created), (1, 1))
            self.assertEqual(second.puc_alerts_created, 0)
            self.assertEqual(puc.create_calls, 2)

    def test_injected_api_reads_prepared_snapshot_without_refresh_or_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            reader, puc = _Reader(), _PucRepository()
            runtime = self._runtime(directory, reader, puc); self.assertTrue(runtime.refresh().succeeded)
            before = (len(reader.event_calls), puc.create_calls)
            app = runtime.create_app()
            async def calls():
                transport = httpx.ASGITransport(app=app)
                async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                    return (await client.get("/v1/health"), await client.get("/v1/trajectories"),
                            await client.get("/v1/dashboard"), await client.get("/v1/gis/cameras"))
            health, trajectories, dashboard, cameras = asyncio.run(calls())
            self.assertEqual((health.status_code, trajectories.status_code, dashboard.status_code, cameras.status_code), (200, 200, 200, 200))
            self.assertEqual(health.json()["runtime"]["mode"], "REAL_SUPABASE")
            self.assertEqual(before, (len(reader.event_calls), puc.create_calls))
            self.assertEqual(trajectories.json()["items"][0]["events"][0]["event_date"], "2025-01-01")
            properties = cameras.json()["features"][0]["properties"]
            self.assertEqual((properties["camera_id"], properties["source_camera_id"], properties["coordinate_provenance"]),
                             ("Camera_1", "1", "SUPABASE"))

    def test_failed_refresh_keeps_prior_service_and_store(self):
        with tempfile.TemporaryDirectory() as directory:
            reader = _Reader(); runtime = self._runtime(directory, reader)
            self.assertTrue(runtime.refresh().succeeded)
            prior_service = runtime.service
            contents = (Path(directory) / "runtime.json").read_bytes()
            reader.fail = True
            failed = runtime.refresh()
            self.assertFalse(failed.succeeded)
            self.assertIs(runtime.service, prior_service)
            self.assertTrue(runtime.status.snapshot_ready)
            self.assertFalse(runtime.status.last_refresh_succeeded)
            self.assertEqual((Path(directory) / "runtime.json").read_bytes(), contents)

    def test_malformed_rows_are_rejected_safely_and_offset_is_honored(self):
        with tempfile.TemporaryDirectory() as directory:
            events = [{"id": 1}, *_Reader().events]
            reader = _Reader(events); runtime = self._runtime(directory, reader, event_limit=2, event_offset=0)
            result = runtime.refresh()
            self.assertTrue(result.succeeded)
            self.assertEqual(reader.event_calls, [(2, 0)])
            self.assertEqual(result.source_event_count, 1)


if __name__ == "__main__":
    unittest.main()
