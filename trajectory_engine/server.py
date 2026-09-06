"""
Phase 10 production-style server entrypoint.

This module:
1. Builds the Phase 10 runtime from environment variables.
2. Uses the configured Supabase/PostgreSQL connection.
3. Loads the synthetic demo network by default.
4. Performs one explicit refresh before starting the API.
5. Exposes the Phase 9 FastAPI application through uvicorn.

Environment variables:
    TRAJECTORY_STORE
    TRAJECTORY_NETWORK_CONFIG
    TRAJECTORY_CAMERA_LIMIT
    TRAJECTORY_EVENT_LIMIT
    TRAJECTORY_EVENT_OFFSET
    TRAJECTORY_HOST
    TRAJECTORY_PORT
"""

from __future__ import annotations

import os
from pathlib import Path

import uvicorn

from database import get_connection
from runtime import Phase10Runtime, RuntimeConfig


BASE_DIR = Path(__file__).resolve().parent


def _env_int(name: str, default: int) -> int:
    """Read an integer environment variable with a safe default."""
    value = os.getenv(name)

    if value is None or value.strip() == "":
        return default

    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(
            f"Environment variable {name!r} must be an integer, "
            f"got {value!r}"
        ) from exc


def build_runtime() -> Phase10Runtime:
    """
    Build the Phase 10 runtime using the real Supabase/PostgreSQL
    connection and the configured trajectory network.
    """

    store_path = Path(
        os.getenv(
            "TRAJECTORY_STORE",
            str(BASE_DIR / "runtime_store.json"),
        )
    )

    network_config_value = os.getenv(
        "TRAJECTORY_NETWORK_CONFIG",
        str(BASE_DIR / "config" / "demo_network.json"),
    )

    network_config_path = Path(network_config_value)

    config = RuntimeConfig(
        repository_path=store_path,
        camera_limit=_env_int("TRAJECTORY_CAMERA_LIMIT", 1000),
        event_limit=_env_int("TRAJECTORY_EVENT_LIMIT", 1000),
        event_offset=_env_int("TRAJECTORY_EVENT_OFFSET", 0),
        network_config_path=network_config_path,
    )

    return Phase10Runtime(
        config=config,
        connection_factory=get_connection,
    )


def build_app():
    """
    Build the FastAPI application after performing one real-data refresh.

    The refresh is intentionally explicit here so that the API starts
    only after the trajectory snapshot has been prepared.
    """

    runtime = build_runtime()

    refresh_result = runtime.refresh()

    if not refresh_result.succeeded:
        raise RuntimeError(
            "Phase 10 runtime refresh failed. "
            f"Refresh result: {refresh_result}"
        )

    return runtime.create_app()


app = build_app()


def main() -> None:
    """Start the FastAPI server with uvicorn."""

    host = os.getenv("TRAJECTORY_HOST", "127.0.0.1")
    port = _env_int("TRAJECTORY_PORT", 8000)

    uvicorn.run(
        app,
        host=host,
        port=port,
    )


if __name__ == "__main__":
    main()
