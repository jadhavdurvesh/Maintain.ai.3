from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from .. import models, audit
from ..database import get_db
from ..deps import get_current_user, CurrentUser

router = APIRouter(prefix="/api/devices", tags=["devices-safety"])


READING_ALIASES = {
    "motor_current": "current",
    "motor-current": "current",
    "machine_load": "load",
    "machine-load": "load",
}


class SafetyPolicyPayload(BaseModel):
    enabled: bool = False
    monitored_reading_type: str = "temperature"
    unit: str | None = None
    warning_low: float | None = None
    warning_high: float | None = None
    shutdown_low: float | None = None
    shutdown_high: float | None = None
    auto_shutdown_enabled: bool = False


def _normalize_signal(value: str | None) -> str:
    key = (value or "").strip().lower()
    return READING_ALIASES.get(key, key)


def _machine(db: Session, machine_id: int, current: CurrentUser, admin_only: bool = False):
    if admin_only and current.role != models.UserRole.admin.value:
        raise HTTPException(403, "administrator access required")
    machine = (
        db.query(models.Machine)
        .filter(
            models.Machine.id == machine_id,
            models.Machine.organization_id == current.organization_id,
            models.Machine.archived.is_(False),
        )
        .first()
    )
    if not machine:
        raise HTTPException(404, "machine not found")
    if current.role == models.UserRole.technician.value:
        assigned = (
            db.query(models.UserMachineAssignment)
            .filter_by(user_id=current.id, machine_id=machine_id)
            .first()
        )
        if not assigned:
            raise HTTPException(404, "machine not assigned to this worker")
    return machine


def _rows(db: Session, machine_id: int):
    policies = (
        db.query(models.MachineSafetyPolicy)
        .filter_by(machine_id=machine_id)
        .order_by(models.MachineSafetyPolicy.id.asc())
        .all()
    )
    columns = [
        c for c in models.MachineSafetyPolicy.__table__.columns
        if c.name not in {"id", "machine_id"}
    ]
    return [{c.name: getattr(policy, c.name) for c in columns} for policy in policies]


@router.get("/{machine_id}/safety")
def get_safety(machine_id: int, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    machine = _machine(db, machine_id, current)
    rows = _rows(db, machine.id)
    return {
        "configured": bool(rows),
        "enabled": any(bool(row.get("enabled")) for row in rows),
        "policies": rows,
        "auto_shutdown_enabled": any(bool(row.get("auto_shutdown_enabled")) for row in rows),
    }


@router.put("/{machine_id}/safety")
def save_safety(
    machine_id: int,
    payload: SafetyPolicyPayload,
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    machine = _machine(db, machine_id, current, admin_only=True)
    signal = _normalize_signal(payload.monitored_reading_type)

    if not signal:
        raise HTTPException(400, "A monitored safety signal is required.")
    if payload.auto_shutdown_enabled and not payload.enabled:
        raise HTTPException(400, "Enable threshold monitoring before enabling automatic shutdown.")
    if payload.shutdown_low is not None and payload.warning_low is not None and payload.warning_low < payload.shutdown_low:
        raise HTTPException(400, "Low warning threshold must be reached before the low shutdown threshold.")
    if payload.shutdown_high is not None and payload.warning_high is not None and payload.warning_high > payload.shutdown_high:
        raise HTTPException(400, "High warning threshold must be reached before the high shutdown threshold.")
    if payload.shutdown_low is not None and payload.shutdown_high is not None and payload.shutdown_low >= payload.shutdown_high:
        raise HTTPException(400, "Low shutdown threshold must be below high shutdown threshold.")

    try:
        policy = (
            db.query(models.MachineSafetyPolicy)
            .filter_by(machine_id=machine.id, monitored_reading_type=signal)
            .order_by(models.MachineSafetyPolicy.id.asc())
            .first()
        )
        if policy is None:
            policy = models.MachineSafetyPolicy(
                machine_id=machine.id,
                monitored_reading_type=signal,
            )
            db.add(policy)

        values = payload.model_dump()
        values["monitored_reading_type"] = signal
        for key, value in values.items():
            setattr(policy, key, value)
        policy.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(policy)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            409,
            "Safety settings could not be saved because another safety policy update conflicted. Please retry.",
        ) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        print(f"[safety] policy database write failed: {type(exc).__name__}: {exc}")
        raise HTTPException(
            500,
            "Safety settings could not be saved because the safety policy database write failed.",
        ) from exc

    # Audit is deliberately best-effort. A broken audit row must never turn a
    # successfully persisted safety interlock into a false 500 response.
    try:
        audit.log_event(
            db,
            "machine",
            machine.id,
            "safety_policy_updated",
            f"Safety thresholds updated for {machine.name} ({signal})",
            organization_id=current.organization_id,
        )
    except Exception as exc:
        db.rollback()
        print(f"[safety] audit write failed after policy save: {type(exc).__name__}: {exc}")

    rows = _rows(db, machine.id)
    saved = next((row for row in rows if row.get("monitored_reading_type") == signal), None)
    if saved is None:
        raise HTTPException(500, "Safety settings were saved but the updated policy could not be reloaded.")

    return {
        "configured": True,
        "policies": rows,
        **saved,
    }
