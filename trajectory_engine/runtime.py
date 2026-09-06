"""Operator-controlled Phase 10 Supabase refresh and FastAPI composition.

One invocation performs one bounded refresh. It never starts a scheduler and
does not let HTTP GET handlers trigger ingestion or PUC synchronization.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import os
from pathlib import Path
import tempfile
from typing import Any, Callable

from demo_network import load_demo_network
from api import create_app
from supabase_repository import SupabaseEventReader, SupabasePucRepository
from logging_utils import logger
from data_pipeline import ReadOnlyDatabasePipeline
from trajectory_service import Phase9Service
from trajectory_repository import Phase7TrajectoryRepository


@dataclass(frozen=True)
class RuntimeConfig:
    """Configuration for one Phase 10 runtime."""

    repository_path: Path
    camera_limit: int = 1000
    event_limit: int = 1000
    event_offset: int = 0
    network_config_path: Path | None = None

    def __post_init__(self) -> None:
        if (
            not 1 <= self.camera_limit <= 10000
            or not 1 <= self.event_limit <= 10000
            or self.event_offset < 0
        ):
            raise ValueError(
                "camera_limit/event_limit must be 1..10000 "
                "and event_offset must be non-negative"
            )


@dataclass
class RuntimeStatus:
    """Public runtime status exposed to the API."""

    mode: str = "REAL_SUPABASE"
    network_provenance: str = "DEMO_NETWORK"
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
    """Result of one explicit refresh."""

    succeeded: bool
    source_event_count: int
    trajectory_count: int
    puc_checked_count: int
    puc_alerts_created: int
    error_type: str | None = None


class Phase10Runtime:
    """Compose the existing Phase 9 components without duplicating engine logic."""

    def __init__(
        self,
        config: RuntimeConfig,
        connection_factory: Callable[[], Any],
        *,
        reader: SupabaseEventReader | None = None,
        puc_repository: SupabasePucRepository | None = None,
    ) -> None:
        self.config = config
        self.reader = reader or SupabaseEventReader(connection_factory)
        self.puc_repository = (
            puc_repository
            or SupabasePucRepository(connection_factory)
        )
        self.service: Phase9Service | None = None
        self.status = RuntimeStatus()

    def refresh(self) -> RefreshResult:
        """Run one bounded refresh.

        The previous valid store/service remains untouched if the refresh
        fails before the final atomic replacement.
        """

        staging_path = self._staging_path()

        try:
            # ---------------------------------------------------------
            # 1. Read cameras from Supabase.
            # ---------------------------------------------------------
            cameras = self.reader.fetch_cameras(
                limit=self.config.camera_limit
            )

            camera_map, service_cameras = self._camera_maps(cameras)

            # Build this before reconstruction: the legacy validation adapter
            # must receive the same runtime network later used by analytics.
            network = self._build_network(service_cameras)

            # ---------------------------------------------------------
            # 2. Build a temporary trajectory repository.
            # ---------------------------------------------------------
            staging_repository = Phase7TrajectoryRepository(staging_path)

            # ---------------------------------------------------------
            # 3. Build the existing read-only database pipeline.
            # ---------------------------------------------------------
            pipeline = ReadOnlyDatabasePipeline(
                self.reader,
                staging_repository,
                camera_map,
                self.puc_repository,
            )

            # ---------------------------------------------------------
            # 4. Fetch and normalize bounded plate events.
            # ---------------------------------------------------------
            events, source = pipeline.fetch_and_normalize(
                limit=self.config.event_limit,
                offset=self.config.event_offset,
            )

            # ---------------------------------------------------------
            # 5. Reconstruct trajectories using the existing engine.
            # ---------------------------------------------------------
            reconstruction = pipeline.reconstruct_to_local_repository(
                events,
                network=network,
            )

            # ---------------------------------------------------------
            # 6. Synchronize PUC-related alerts.
            # ---------------------------------------------------------
            puc = pipeline.synchronize_puc_alerts()

            # ---------------------------------------------------------
            # 7. Ensure the staging trajectory store exists.
            # ---------------------------------------------------------
            if not staging_path.exists():
                raise RuntimeError(
                    "Refresh did not create a local trajectory store"
                )

            # ---------------------------------------------------------
            # 8. Build the Phase 9 service with the selected network.
            # ---------------------------------------------------------
            service = Phase9Service(
                staging_repository,
                network=network,
                cameras=service_cameras,
                puc_repository=self.puc_repository,
            )

            # ---------------------------------------------------------
            # 9. Calculate all Phase 8/9 analytics.
            # ---------------------------------------------------------
            service.refresh()

            # ---------------------------------------------------------
            # 10. Atomically replace the final local snapshot.
            # ---------------------------------------------------------
            self.config.repository_path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            os.replace(
                staging_path,
                self.config.repository_path,
            )

            # ---------------------------------------------------------
            # 11. Point the service at the final snapshot.
            # ---------------------------------------------------------
            service.repository = Phase7TrajectoryRepository(
                self.config.repository_path
            )

            self.service = service

            # ---------------------------------------------------------
            # 12. Update public runtime status.
            # ---------------------------------------------------------
            self.status.snapshot_ready = True
            self.status.last_refresh_succeeded = True
            self.status.last_successful_refresh_at = (
                datetime.now(timezone.utc).isoformat()
            )
            self.status.source_event_count = source["accepted_count"]
            self.status.trajectory_count = reconstruction[
                "trajectory_count"
            ]
            self.status.puc_checked_count = puc["checked_count"]
            self.status.puc_alerts_created = puc["alerts_created"]
            self.status.last_error_type = None

            return RefreshResult(
                True,
                self.status.source_event_count,
                self.status.trajectory_count,
                self.status.puc_checked_count,
                self.status.puc_alerts_created,
            )

        except Exception as exc:
            self.status.last_refresh_succeeded = False
            self.status.last_error_type = type(exc).__name__

            logger.exception(
                "phase10_refresh_failed error_type=%s",
                self.status.last_error_type,
            )

            return RefreshResult(
                False,
                self.status.source_event_count,
                self.status.trajectory_count,
                self.status.puc_checked_count,
                self.status.puc_alerts_created,
                self.status.last_error_type,
            )

        finally:
            # If the staging file still exists, remove it.
            if staging_path.exists():
                staging_path.unlink()

    def _build_network(
        self,
        service_cameras: dict[str, dict[str, Any]],
    ):
        """Build the trajectory network for the current runtime."""

        # Preserve existing behavior when no explicit network config
        # is supplied. This is useful for the existing Phase 10 tests.
        if self.config.network_config_path is None:
            self.status.network_provenance = "DEVELOPMENT_FIXTURE"

            from network import ProductionCameraNetwork

            return ProductionCameraNetwork.from_development_graph()

        # Production/demo runtime path:
        # load the configured directed network and overlay the actual
        # Supabase camera set/coordinates.
        network = load_demo_network(
            self.config.network_config_path,
            camera_overrides=service_cameras,
        )

        self.status.network_provenance = "DEMO_NETWORK"

        return network

    def create_app(self):
        """Create the FastAPI application after a successful refresh."""

        if self.service is None:
            raise RuntimeError(
                "A successful explicit refresh is required before "
                "creating the real runtime API"
            )

        return create_app(
            self.service,
            runtime_status_provider=self.status.public,
        )

    def _staging_path(self) -> Path:
        """Create a temporary path next to the final repository."""

        self.config.repository_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        prefix = f".{self.config.repository_path.name}.phase10-"

        handle = tempfile.NamedTemporaryFile(
            prefix=prefix,
            suffix=".json",
            dir=self.config.repository_path.parent,
            delete=False,
        )

        handle.close()

        path = Path(handle.name)

        # Phase7TrajectoryRepository expects to create the file itself.
        path.unlink()

        return path

    @staticmethod
    def _camera_maps(
        cameras: list[dict[str, Any]],
    ) -> tuple[
        dict[str, str],
        dict[str, dict[str, Any]],
    ]:
        """Convert Supabase camera rows into pipeline/service mappings."""

        id_to_name: dict[str, str] = {}
        named: dict[str, dict[str, Any]] = {}

        for camera in cameras:
            camera_id = str(camera["id"])
            name = str(camera["name"])

            if not name or name in named:
                raise ValueError(
                    "Supabase cameras require unique usable names"
                )

            id_to_name[camera_id] = name

            named[name] = {
                "id": camera_id,
                "name": name,
                "lat": camera["lat"],
                "lon": camera["lon"],
                "coordinate_provenance": camera[
                    "coordinate_provenance"
                ],
            }

        return id_to_name, named


def main() -> int:
    """Run one explicit bounded Phase 10 refresh."""

    from argparse import ArgumentParser
    from database import get_connection

    parser = ArgumentParser(
        description=(
            "Run one bounded SIH26127 Phase 10 "
            "Supabase refresh"
        )
    )

    parser.add_argument(
        "--store",
        default="phase10_runtime_store.json",
    )

    parser.add_argument(
        "--camera-limit",
        type=int,
        default=1000,
    )

    parser.add_argument(
        "--event-limit",
        type=int,
        default=1000,
    )

    parser.add_argument(
        "--event-offset",
        type=int,
        default=0,
    )

    parser.add_argument(
        "--network-config",
        default=str(
            Path(__file__).parent.parent / "config" / "demo_network.json"
        ),
    )

    args = parser.parse_args()

    runtime = Phase10Runtime(
        RuntimeConfig(
            repository_path=Path(args.store),
            camera_limit=args.camera_limit,
            event_limit=args.event_limit,
            event_offset=args.event_offset,
            network_config_path=Path(args.network_config),
        ),
        get_connection,
    )

    result = runtime.refresh()

    print(f"mode={runtime.status.mode}")
    print(
        f"network_provenance="
        f"{runtime.status.network_provenance}"
    )
    print(
        f"refresh="
        f"{'PASS' if result.succeeded else 'FAIL'}"
    )
    print(
        f"source_events="
        f"{result.source_event_count}"
    )
    print(
        f"trajectories="
        f"{result.trajectory_count}"
    )
    print(
        f"puc_checked="
        f"{result.puc_checked_count}"
    )
    print(
        f"puc_alerts_created="
        f"{result.puc_alerts_created}"
    )
    print(
        f"snapshot_ready="
        f"{runtime.status.snapshot_ready}"
    )

    if not result.succeeded:
        print(
            f"error_type="
            f"{result.error_type}"
        )

    return 0 if result.succeeded else 1


if __name__ == "__main__":
    raise SystemExit(main())
