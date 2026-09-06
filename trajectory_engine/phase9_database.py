"""Supabase/PostgreSQL adapter for Phase 9 source reads and explicit PUC alerts.

Source events and cameras are read-only.  The only write is an explicit,
parameterized ``PUC_UNVERIFIED`` alert insert; it never alters trajectory or
source-event data and never changes schema.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

from phase9_logging import logger, timed
from puc_verification import PUC_ALERT_TYPE, PucVerificationResult


class DataAccessError(RuntimeError):
    """Safe application-facing database failure; no credential information."""


class SupabaseEventReader:
    def __init__(self, connection_factory: Callable[[], Any]) -> None:
        self._connection_factory = connection_factory

    def fetch_events(self, *, limit: int = 1000, offset: int = 0,
                     start_time: datetime | None = None, end_time: datetime | None = None) -> list[dict[str, Any]]:
        if not 1 <= limit <= 10000 or offset < 0:
            raise ValueError("limit must be 1..10000 and offset must be non-negative")
        clauses, parameters = [], []
        if start_time:
            clauses.append("plate_events.event_time >= %s"); parameters.append(start_time)
        if end_time:
            clauses.append("plate_events.event_time <= %s"); parameters.append(end_time)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        query = """SELECT plate_events.id, plate_events.plate_number, plate_events.camera_id,
            cameras.name, ST_Y(cameras.location::geometry), ST_X(cameras.location::geometry),
            plate_events.event_time, plate_events.confidence
            FROM plate_events JOIN cameras ON plate_events.camera_id = cameras.id""" + where + \
            " ORDER BY plate_events.event_time, plate_events.id LIMIT %s OFFSET %s"
        parameters.extend([limit, offset])
        try:
            with timed("database_fetch_events", limit=limit, offset=offset):
                connection = self._connection_factory()
                try:
                    with connection.cursor() as cursor:
                        cursor.execute(query, parameters)
                        rows = cursor.fetchall()
                finally:
                    connection.close()
        except Exception as exc:
            logger.warning("database_read_failed operation=fetch_events error_type=%s", type(exc).__name__)
            raise DataAccessError("Database events are currently unavailable") from exc
        events = []
        for row in rows:
            try:
                timestamp = row[6].strftime("%H:%M:%S") if hasattr(row[6], "strftime") else str(row[6])
                event_timestamp = row[6].isoformat() if hasattr(row[6], "isoformat") else str(row[6])
                event_date = row[6].date().isoformat() if hasattr(row[6], "date") else str(row[6])[:10]
                events.append({"id": row[0], "plate_number": row[1], "camera_id": str(row[2]),
                    "camera_name": row[3], "latitude": row[4], "longitude": row[5],
                    "timestamp": timestamp, "event_timestamp": event_timestamp,
                    "event_date": event_date, "confidence": float(row[7])})
            except (TypeError, ValueError, IndexError):
                logger.warning("database_record_skipped reason=malformed_row")
        logger.info("database_read_completed records=%s", len(events))
        return events

    def fetch_cameras(self, *, limit: int = 10000) -> list[dict[str, Any]]:
        if not 1 <= limit <= 10000:
            raise ValueError("limit must be 1..10000")
        query = ("SELECT id, name, ST_Y(location::geometry), ST_X(location::geometry) "
                 "FROM cameras ORDER BY id LIMIT %s")
        try:
            with timed("database_fetch_cameras", limit=limit):
                connection = self._connection_factory()
                try:
                    with connection.cursor() as cursor:
                        cursor.execute(query, [limit])
                        rows = cursor.fetchall()
                finally:
                    connection.close()
        except Exception as exc:
            logger.warning("database_read_failed operation=fetch_cameras error_type=%s", type(exc).__name__)
            raise DataAccessError("Database cameras are currently unavailable") from exc
        cameras = []
        for row in rows:
            try:
                cameras.append({"id": str(row[0]), "name": str(row[1]), "lat": float(row[2]), "lon": float(row[3]),
                                "coordinate_provenance": "SUPABASE"})
            except (TypeError, ValueError, IndexError):
                logger.warning("database_camera_skipped reason=malformed_row")
        return cameras


class SupabasePucRepository:
    """Explicit bounded PUC/alert operations; no trajectory data is written."""
    def __init__(self, connection_factory: Callable[[], Any]) -> None:
        self._connection_factory = connection_factory

    @staticmethod
    def _normalized_where(column: str) -> str:
        return f"regexp_replace(upper({column}), '[^A-Z0-9]', '', 'g') = %s"

    def fetch_records(self, normalized_plate: str) -> list[dict[str, Any]]:
        query = ("SELECT id, plate_number, puc_expiry_date, status FROM puc_records WHERE "
                 + self._normalized_where("plate_number")
                 + " ORDER BY puc_expiry_date DESC NULLS LAST, id DESC LIMIT %s")
        return self._fetch_rows(query, [normalized_plate, 100], "database_fetch_puc_records", self._row_to_puc)

    def fetch_unresolved_alert(self, normalized_plate: str) -> dict[str, Any] | None:
        query = ("SELECT id, plate_number, alert_type, severity, message, is_resolved FROM alerts WHERE "
                 + self._normalized_where("plate_number")
                 + " AND alert_type = %s AND is_resolved = FALSE ORDER BY id DESC LIMIT 1")
        rows = self._fetch_rows(query, [normalized_plate, PUC_ALERT_TYPE], "database_fetch_unresolved_puc_alert", self._row_to_alert)
        return rows[0] if rows else None

    def list_puc_alerts(self, *, limit: int = 1000, offset: int = 0) -> list[dict[str, Any]]:
        if not 1 <= limit <= 10000 or offset < 0:
            raise ValueError("limit must be 1..10000 and offset must be non-negative")
        query = ("SELECT id, plate_number, alert_type, severity, message, is_resolved FROM alerts "
                 "WHERE alert_type = %s ORDER BY id DESC LIMIT %s OFFSET %s")
        return self._fetch_rows(query, [PUC_ALERT_TYPE, limit, offset], "database_list_puc_alerts", self._row_to_alert)

    def create_alert_if_absent(self, result: PucVerificationResult) -> tuple[dict[str, Any] | None, bool]:
        """Application-level idempotency; concurrent workers remain a documented limitation."""
        if not result.alert_required:
            return None, False
        connection = None
        try:
            with timed("database_sync_puc_alert", outcome=result.outcome):
                connection = self._connection_factory()
                try:
                    with connection.cursor() as cursor:
                        existing_query = ("SELECT id, plate_number, alert_type, severity, message, is_resolved FROM alerts WHERE "
                                          + self._normalized_where("plate_number")
                                          + " AND alert_type = %s AND is_resolved = FALSE ORDER BY id DESC LIMIT 1")
                        cursor.execute(existing_query, [result.normalized_plate, PUC_ALERT_TYPE])
                        existing = cursor.fetchone()
                        if existing:
                            return self._row_to_alert(existing), False
                        insert = ("INSERT INTO alerts (plate_number, alert_type, severity, message, is_resolved) "
                                  "VALUES (%s, %s, %s, %s, FALSE) "
                                  "RETURNING id, plate_number, alert_type, severity, message, is_resolved")
                        cursor.execute(insert, [result.normalized_plate, PUC_ALERT_TYPE, result.severity, result.message])
                        created = cursor.fetchone()
                    connection.commit()
                    return self._row_to_alert(created), True
                except Exception:
                    connection.rollback()
                    raise
                finally:
                    connection.close()
        except Exception as exc:
            logger.warning("database_puc_alert_sync_failed error_type=%s", type(exc).__name__)
            raise DataAccessError("PUC alert synchronization is currently unavailable") from exc

    def _fetch_rows(self, query: str, parameters: list[Any], operation: str,
                    mapper: Callable[[Any], dict[str, Any]]) -> list[dict[str, Any]]:
        try:
            with timed(operation):
                connection = self._connection_factory()
                try:
                    with connection.cursor() as cursor:
                        cursor.execute(query, parameters)
                        rows = cursor.fetchall()
                finally:
                    connection.close()
            return [mapper(row) for row in rows]
        except Exception as exc:
            logger.warning("database_read_failed operation=%s error_type=%s", operation, type(exc).__name__)
            raise DataAccessError("Database PUC data is currently unavailable") from exc

    @staticmethod
    def _row_to_puc(row: Any) -> dict[str, Any]:
        return {"id": row[0], "plate_number": row[1], "puc_expiry_date": row[2], "status": row[3]}

    @staticmethod
    def _row_to_alert(row: Any) -> dict[str, Any]:
        return {"alert_id": row[0], "plate_number": row[1], "alert_type": row[2],
                "severity": row[3], "message": row[4], "is_resolved": row[5]}
