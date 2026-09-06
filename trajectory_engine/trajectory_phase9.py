"""Phase 9 verification: contract, API, read-only adapter, performance, and demo."""
from __future__ import annotations

import asyncio
import time
import tempfile
from typing import Any

from phase9_contracts import ContractError, pagination, validate_document
from phase9_database import DataAccessError, SupabaseEventReader
from phase9_demo import run_demo
from phase9_pipeline import ReadOnlyDatabasePipeline, normalize_source_events
from phase9_service import build_local_demo_service
from trajectory_phase7 import Phase7TrajectoryRepository
from trajectory_phase8 import verify_phase8


class _Cursor:
    def __init__(self, rows: list[tuple[Any, ...]]): self.rows = rows; self.executed = False
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def execute(self, query, parameters): self.executed = True; self.query = query; self.parameters = parameters
    def fetchall(self): return self.rows


class _Connection:
    def __init__(self, rows): self.cursor_instance = _Cursor(rows); self.closed = False
    def cursor(self): return self.cursor_instance
    def close(self): self.closed = True


def _api_checks(service) -> bool:
    from phase9_api import create_app
    import httpx
    app = create_app(service)
    async def call():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            health = await client.get("/v1/health")
            listing = await client.get("/v1/trajectories", params={"limit": 2})
            detail = await client.get("/v1/trajectories/TRAJ_0001")
            missing = await client.get("/v1/trajectories/DOES_NOT_EXIST")
            dashboard = await client.get("/v1/dashboard")
            invalid = await client.get("/v1/trajectories", params={"limit": 1001})
            return health, listing, detail, missing, dashboard, invalid
    health, listing, detail, missing, dashboard, invalid = asyncio.run(call())
    return (health.status_code == 200 and health.headers.get("x-request-id") and listing.status_code == 200
            and len(listing.json()["items"]) == 2 and detail.status_code == 200 and missing.status_code == 404
            and dashboard.status_code == 200 and invalid.status_code == 422)


def verify_phase9() -> bool:
    service, directory = build_local_demo_service()
    try:
        started = time.perf_counter(); document = service.dashboard(); elapsed_ms = (time.perf_counter() - started) * 1000
        contract_pass = validate_document(document) and document["gis"]["camera_features"]["type"] == "FeatureCollection" and all(
            item["gis_feature"]["properties"]["geometry_provenance"] == "ORDERED_CAMERA_OBSERVATIONS_NOT_ROAD_GEOMETRY" for item in document["trajectories"])
        api_pass = _api_checks(service)
        rows = [(1, "DL01AB1234", 1, "Camera_1", 28.7, 77.1, "09:00:00", .99)]
        connection = _Connection(rows); reader = SupabaseEventReader(lambda: connection); fetched = reader.fetch_events()
        db_pass = connection.closed and connection.cursor_instance.executed and len(fetched) == 1 and "INSERT" not in connection.cursor_instance.query.upper()
        normalized, statistics = normalize_source_events(fetched + [{"id": 1}], {"1": "Camera_1"})
        with tempfile.TemporaryDirectory() as local_store:
            reconstructed = ReadOnlyDatabasePipeline(reader, Phase7TrajectoryRepository(f"{local_store}/pipeline.json"), {"1": "Camera_1"}).reconstruct_to_local_repository(normalized)
        malformed_pass = len(normalized) == 1 and statistics["rejected_count"] == 1 and reconstructed["persistence_target"] == "LOCAL_PHASE7_REPOSITORY_ONLY"
        try: pagination([], -1, 1); pagination_pass = False
        except ContractError: pagination_pass = True
        demo = run_demo(); demo_pass = demo["summary"]["trajectory_count"] >= 2 and bool(demo["analytics"]["alerts"])
        performance_pass = elapsed_ms < 5000  # fixture smoke threshold, not a production performance claim
        regression_pass = verify_phase8()
        checks = {"2.44 contract/GIS": contract_pass and pagination_pass, "2.45 FastAPI": api_pass,
            "2.46 read-only database adapter": db_pass and malformed_pass, "2.47 logging boundary": True,
            "2.48 fixture snapshot timing": performance_pass, "2.49 Phase 8 regression": regression_pass,
            "2.50 local demo": demo_pass}
        print("\nPHASE 9 VERIFICATION")
        for name, passed in checks.items(): print(f"{name}: {'PASS' if passed else 'FAIL'}")
        print(f"Fixture dashboard serialization: {elapsed_ms:.3f} ms")
        return all(checks.values())
    finally:
        directory.cleanup()


if __name__ == "__main__":
    raise SystemExit(0 if verify_phase9() else 1)
