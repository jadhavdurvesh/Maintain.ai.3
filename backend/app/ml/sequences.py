"""Build contiguous temporal sequences for Phase 2 predictive-maintenance training.

The sequence contains only telemetry windows at or before the prediction point.
The target comes exclusively from the future outcome label, preventing leakage.
"""
import json
from datetime import timedelta
from sqlalchemy.orm import Session
from .. import models

SEQUENCE_LENGTH = 24
WINDOW_SECONDS = 3600
HORIZONS = (24 * 3600, 48 * 3600, 7 * 24 * 3600)

def build_sequences_for_machine(db: Session, machine_id: int, limit: int = 5000):
    windows = (
        db.query(models.MLTelemetryWindow)
        .filter(models.MLTelemetryWindow.machine_id == machine_id,
                models.MLTelemetryWindow.window_seconds == WINDOW_SECONDS)
        .order_by(models.MLTelemetryWindow.window_end.asc(), models.MLTelemetryWindow.id.asc())
        .limit(limit).all()
    )
    created = 0
    for end_index in range(SEQUENCE_LENGTH - 1, len(windows)):
        end = windows[end_index]
        start = windows[end_index - SEQUENCE_LENGTH + 1]
        expected_start = end.window_end - timedelta(seconds=(SEQUENCE_LENGTH - 1) * WINDOW_SECONDS)
        if start.window_end != expected_start:
            continue

        for horizon in HORIZONS:
            label = (
                db.query(models.MLTrainingLabel)
                .filter_by(machine_id=machine_id, window_end=end.window_end,
                           window_seconds=WINDOW_SECONDS, horizon_seconds=horizon)
                .first()
            )
            if not label:
                continue

            payload = []
            for window in windows[end_index - SEQUENCE_LENGTH + 1:end_index + 1]:
                payload.append(json.loads(window.feature_json))

            row = (
                db.query(models.MLSequenceSample)
                .filter_by(machine_id=machine_id, end_window_id=end.id,
                           sequence_length=SEQUENCE_LENGTH, horizon_seconds=horizon)
                .first()
            )
            data = json.dumps(payload, separators=(",", ":"))
            if row:
                row.sequence_json = data
                row.target_failure = bool(label.fault_within_horizon or label.breakdown_work_order_within_horizon)
                row.fault_id = label.fault_id
            else:
                db.add(models.MLSequenceSample(
                    machine_id=machine_id, end_window_id=end.id, window_end=end.window_end,
                    window_seconds=WINDOW_SECONDS, sequence_length=SEQUENCE_LENGTH,
                    horizon_seconds=horizon, sequence_json=data,
                    target_failure=bool(label.fault_within_horizon or label.breakdown_work_order_within_horizon),
                    fault_id=label.fault_id,
                ))
            created += 1
    db.commit()
    return {"machine_id": machine_id, "sequences_created_or_updated": created,
            "sequence_length": SEQUENCE_LENGTH, "window_seconds": WINDOW_SECONDS,
            "horizons_seconds": list(HORIZONS)}
