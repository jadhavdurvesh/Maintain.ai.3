"""Point-in-time labels for Phase 2 predictive-maintenance training.

Only events after a telemetry window ends are used, preventing future leakage.
Incomplete future horizons are not labeled as negatives.
"""
from datetime import timedelta
from sqlalchemy.orm import Session
from .. import models

HORIZONS = (24 * 3600, 48 * 3600, 7 * 24 * 3600, 30 * 24 * 3600)

def label_window(db: Session, machine_id: int, window_end, window_seconds: int):
    labels = []
    for horizon in HORIZONS:
        horizon_end = window_end + timedelta(seconds=horizon)
        fault = (
            db.query(models.FaultRecord)
            .filter(models.FaultRecord.machine_id == machine_id,
                    models.FaultRecord.reported_date > window_end,
                    models.FaultRecord.reported_date <= horizon_end)
            .order_by(models.FaultRecord.reported_date.asc(), models.FaultRecord.id.asc())
            .first()
        )
        breakdown = (
            db.query(models.WorkOrder)
            .filter(models.WorkOrder.machine_id == machine_id,
                    models.WorkOrder.created_at > window_end,
                    models.WorkOrder.created_at <= horizon_end,
                    models.WorkOrder.priority == models.Priority.critical)
            .order_by(models.WorkOrder.created_at.asc(), models.WorkOrder.id.asc())
            .first()
        )
        row = (
            db.query(models.MLTrainingLabel)
            .filter_by(machine_id=machine_id, window_end=window_end,
                       window_seconds=window_seconds, horizon_seconds=horizon)
            .first()
        )
        values = {
            "fault_within_horizon": bool(fault),
            "breakdown_work_order_within_horizon": bool(breakdown),
            "fault_id": fault.id if fault else None,
            "work_order_id": breakdown.id if breakdown else None,
        }
        if row:
            for key, value in values.items():
                setattr(row, key, value)
        else:
            db.add(models.MLTrainingLabel(
                machine_id=machine_id, window_end=window_end,
                window_seconds=window_seconds, horizon_seconds=horizon, **values
            ))
        labels.append(row)
    db.flush()
    return labels

def build_labels_for_machine(db: Session, machine_id: int, limit: int = 5000):
    windows = (
        db.query(models.MLTelemetryWindow)
        .filter_by(machine_id=machine_id)
        .order_by(models.MLTelemetryWindow.window_end.asc(), models.MLTelemetryWindow.id.asc())
        .limit(limit).all()
    )
    labeled = 0
    for window in windows:
        latest = (
            db.query(models.SensorReading)
            .filter(models.SensorReading.machine_id == machine_id,
                    models.SensorReading.recorded_at > window.window_end)
            .order_by(models.SensorReading.recorded_at.desc())
            .first()
        )
        if not latest or (latest.recorded_at - window.window_end).total_seconds() < max(HORIZONS):
            continue
        label_window(db, machine_id, window.window_end, window.window_seconds)
        labeled += 1
    db.commit()
    return {"machine_id": machine_id, "windows_labeled": labeled, "horizons_seconds": list(HORIZONS)}
