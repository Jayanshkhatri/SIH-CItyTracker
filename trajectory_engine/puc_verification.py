"""Pure deterministic PUC policy for the existing Supabase demo records."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Iterable

from trajectory_engine import normalize_plate_number


PUC_ALERT_TYPE = "PUC_UNVERIFIED"


@dataclass(frozen=True)
class PucRecord:
    id: int
    plate_number: str
    puc_expiry_date: date | None
    status: str | None


@dataclass(frozen=True)
class PucVerificationResult:
    normalized_plate: str
    reference_date: date
    outcome: str
    alert_required: bool
    severity: str | None
    message: str
    record_id: int | None = None
    expiry_date: date | None = None
    stored_status: str | None = None


def _as_date(value: date | datetime | str | None) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value.strip())
        except ValueError:
            return None
    return None


def normalized_status(value: str | None) -> str:
    return value.strip().upper() if isinstance(value, str) else ""


def record_from_row(row: dict[str, Any]) -> PucRecord:
    return PucRecord(
        id=int(row["id"]),
        plate_number=str(row.get("plate_number") or ""),
        puc_expiry_date=_as_date(row.get("puc_expiry_date")),
        status=row.get("status"),
    )


def select_puc_record(records: Iterable[PucRecord | dict[str, Any]], plate_number: str) -> PucRecord | None:
    """Choose latest non-null expiry, then highest ID; all-null chooses highest ID."""
    plate = normalize_plate_number(plate_number)
    matches = [record_from_row(item) if isinstance(item, dict) else item for item in records]
    matches = [item for item in matches if normalize_plate_number(item.plate_number) == plate]
    if not matches:
        return None
    return max(matches, key=lambda item: (
        item.puc_expiry_date is not None,
        item.puc_expiry_date or date.min,
        item.id,
    ))


def verify_puc(plate_number: str, reference_date: date | datetime | str,
               records: Iterable[PucRecord | dict[str, Any]]) -> PucVerificationResult:
    """Evaluate demo PUC data using the vehicle event date, never current date."""
    plate = normalize_plate_number(plate_number)
    reference = _as_date(reference_date)
    if not plate or reference is None:
        raise ValueError("PUC verification requires a normalized plate and event reference date")
    record = select_puc_record(records, plate)
    if record is None:
        return _result(plate, reference, "RECORD_NOT_FOUND", "MEDIUM", None)
    status = normalized_status(record.status)
    if status != "VALID":
        return _result(plate, reference, "INVALID_STATUS", "HIGH", record)
    if record.puc_expiry_date is None:
        return _result(plate, reference, "MISSING_EXPIRY", "HIGH", record)
    if record.puc_expiry_date < reference:
        return _result(plate, reference, "EXPIRED", "HIGH", record)
    return _result(plate, reference, "VALID", None, record)


def _result(plate: str, reference: date, outcome: str, severity: str | None,
            record: PucRecord | None) -> PucVerificationResult:
    expiry = record.puc_expiry_date.isoformat() if record and record.puc_expiry_date else "UNKNOWN"
    status = normalized_status(record.status) if record else "NOT_FOUND"
    message = (f"PUC {outcome}: plate={plate}; reference_date={reference.isoformat()}; "
               f"expiry_date={expiry}; stored_status={status}.")
    return PucVerificationResult(
        normalized_plate=plate, reference_date=reference, outcome=outcome,
        alert_required=outcome != "VALID", severity=severity, message=message,
        record_id=record.id if record else None,
        expiry_date=record.puc_expiry_date if record else None,
        stored_status=record.status if record else None,
    )
