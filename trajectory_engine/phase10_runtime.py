"""Operator-controlled Phase 10 Supabase refresh and FastAPI composition.

One invocation performs one bounded refresh.  It never starts a scheduler and
does not let HTTP GET handlers trigger ingestion or PUC synchronization.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import os
from pathlib import Path
import tempfile
from typing import Any, Callable

from phase9_api import create_app
from phase9_database import SupabaseEventReader, SupabasePucRepository
from phase9_logging import logger
from phase9_pipeline import ReadOnlyDatabasePipeline
from phase9_service import Phase9Service
from trajectory_phase7 import Phase7TrajectoryRepository


@dataclass(frozen=True)
class RuntimeConfig:
    repository_path: Path
    camera_limit: int = 1000
    event_limit: int = 1000
    event_offset: int = 0

    def __post_init__(self) -> None:
        if not 1 <= self.camera_limit <= 10000 or not 1 <= self.event_limit <= 10000 or self.event_offset < 0:
            raise ValueError("camera_limit/event_limit must be 1..10000 and event_offset must be non-negative")


@dataclass
class RuntimeStatus:
    mode: str = "REAL_SUPABASE"
    snapshot_ready: bool = False
    last_refresh_succeeded: bool = False
    last_successful_refresh_at: str | None = None
    source_event_count: int = 0
    trajectory_count: int = 0
    puc_checked_count: int = 0
    puc_alerts_created: int = 0
    last_error_type: str | None = None

    def public(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RefreshResult:
    succeeded: bool
    source_event_count: int
    trajectory_count: int
    puc_checked_count: int
    puc_alerts_created: int
    error_type: str | None = None


class Phase10Runtime:
    """Compose existing Phase 9 parts without duplicating engine logic."""
    def __init__(self, config: RuntimeConfig, connection_factory: Callable[[], Any], *,
                 reader: SupabaseEventReader | None = None,
                 puc_repository: SupabasePucRepository | None = None) -> None:
        self.config = config
        self.reader = reader or SupabaseEventReader(connection_factory)
        self.puc_repository = puc_repository or SupabasePucRepository(connection_factory)
        self.service: Phase9Service | None = None
        self.status = RuntimeStatus()

    def refresh(self) -> RefreshResult:
        """Run one bounded refresh, retaining the prior valid store/service on error."""
        staging_path = self._staging_path()
        try:
            cameras = self.reader.fetch_cameras(limit=self.config.camera_limit)
            camera_map, service_cameras = self._camera_maps(cameras)
            staging_repository = Phase7TrajectoryRepository(staging_path)
            pipeline = ReadOnlyDatabasePipeline(self.reader, staging_repository, camera_map, self.puc_repository)
            events, source = pipeline.fetch_and_normalize(limit=self.config.event_limit, offset=self.config.event_offset)
            reconstruction = pipeline.reconstruct_to_local_repository(events)
            puc = pipeline.synchronize_puc_alerts()
            if not staging_path.exists():
                raise RuntimeError("Refresh did not create a local trajectory store")
            service = Phase9Service(staging_repository, cameras=service_cameras, puc_repository=self.puc_repository)
            service.refresh()
            self.config.repository_path.parent.mkdir(parents=True, exist_ok=True)
            os.replace(staging_path, self.config.repository_path)
            service.repository = Phase7TrajectoryRepository(self.config.repository_path)
            self.service = service
            self.status.snapshot_ready = True
            self.status.last_refresh_succeeded = True
            self.status.last_successful_refresh_at = datetime.now(timezone.utc).isoformat()
            self.status.source_event_count = source["accepted_count"]
            self.status.trajectory_count = reconstruction["trajectory_count"]
            self.status.puc_checked_count = puc["checked_count"]
            self.status.puc_alerts_created = puc["alerts_created"]
            self.status.last_error_type = None
            return RefreshResult(True, self.status.source_event_count, self.status.trajectory_count,
                                 self.status.puc_checked_count, self.status.puc_alerts_created)
        except Exception as exc:
            self.status.last_refresh_succeeded = False
            self.status.last_error_type = type(exc).__name__
            logger.warning("phase10_refresh_failed error_type=%s", self.status.last_error_type)
            return RefreshResult(False, self.status.source_event_count, self.status.trajectory_count,
                                 self.status.puc_checked_count, self.status.puc_alerts_created,
                                 self.status.last_error_type)
        finally:
            if staging_path.exists():
                staging_path.unlink()

    def create_app(self):
        if self.service is None:
            raise RuntimeError("A successful explicit refresh is required before creating the real runtime API")
        return create_app(self.service, runtime_status_provider=self.status.public)

    def _staging_path(self) -> Path:
        self.config.repository_path.parent.mkdir(parents=True, exist_ok=True)
        prefix = f".{self.config.repository_path.name}.phase10-"
        handle = tempfile.NamedTemporaryFile(prefix=prefix, suffix=".json", dir=self.config.repository_path.parent,
                                             delete=False)
        handle.close()
        path = Path(handle.name)
        path.unlink()
        return path

    @staticmethod
    def _camera_maps(cameras: list[dict[str, Any]]) -> tuple[dict[str, str], dict[str, dict[str, Any]]]:
        id_to_name: dict[str, str] = {}
        named: dict[str, dict[str, Any]] = {}
        for camera in cameras:
            camera_id, name = str(camera["id"]), str(camera["name"])
            if not name or name in named:
                raise ValueError("Supabase cameras require unique usable names")
            id_to_name[camera_id] = name
            named[name] = {"id": camera_id, "name": name, "lat": camera["lat"], "lon": camera["lon"],
                           "coordinate_provenance": camera["coordinate_provenance"]}
        return id_to_name, named


def main() -> int:
    """Explicit one-shot operator command; database credentials stay in ``database.py``."""
    from argparse import ArgumentParser
    from database import get_connection
    parser = ArgumentParser(description="Run one bounded SIH26127 Phase 10 Supabase refresh")
    parser.add_argument("--store", default="phase10_trajectory_store.json")
    parser.add_argument("--camera-limit", type=int, default=1000)
    parser.add_argument("--event-limit", type=int, default=1000)
    parser.add_argument("--event-offset", type=int, default=0)
    args = parser.parse_args()
    runtime = Phase10Runtime(RuntimeConfig(Path(args.store), args.camera_limit, args.event_limit, args.event_offset), get_connection)
    result = runtime.refresh()
    print("mode=REAL_SUPABASE")
    print(f"refresh={'PASS' if result.succeeded else 'FAIL'}")
    print(f"source_events={result.source_event_count}")
    print(f"trajectories={result.trajectory_count}")
    print(f"puc_checked={result.puc_checked_count}")
    print(f"puc_alerts_created={result.puc_alerts_created}")
    print(f"snapshot_ready={runtime.status.snapshot_ready}")
    if not result.succeeded:
        print(f"error_type={result.error_type}")
    return 0 if result.succeeded else 1


if __name__ == "__main__":
    raise SystemExit(main())
