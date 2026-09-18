"""Optional pretrained time-series inference for the MAINTAIN AI local/desktop ML runtime.

The application stays lightweight by keeping pretrained-model dependencies out of the
serverless requirements. When MAINTAIN_PRETRAINED_MODEL_DIR points at a downloaded
TimeRadar checkpoint and its ML dependencies are installed, this adapter provides a
zero-shot anomaly signal. It never trains or changes model weights.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from datetime import datetime, timedelta

MODEL_NAME = "TimeRadar"
SEQUENCE_LENGTH = 100
SENSOR_TYPES = ("temperature", "vibration", "current", "load")


def _model_dir() -> Path:
    configured = os.getenv("MAINTAIN_PRETRAINED_MODEL_DIR", "").strip()
    return Path(configured).expanduser() if configured else Path("backend/app/ml/artifacts/pretrained/TimeRadar")


def pretrained_status() -> dict:
    model_dir = _model_dir()
    deps = True
    reason = None
    try:
        import torch  # noqa: F401
        from transformers import AutoModel  # noqa: F401
    except ImportError as exc:
        deps = False
        reason = f"Optional ML dependencies are not installed: {exc}"
    present = model_dir.exists()
    if not present and reason is None:
        reason = f"Pretrained checkpoint not found at {model_dir}"
    return {
        "model": MODEL_NAME,
        "mode": "zero_shot_anomaly",
        "configured": present and deps,
        "checkpoint_present": present,
        "dependencies_available": deps,
        "sequence_length": SEQUENCE_LENGTH,
        "channels": list(SENSOR_TYPES),
        "reason": reason,
    }


@lru_cache(maxsize=1)
def _load_model():
    from transformers import AutoModel
    import torch

    model = AutoModel.from_pretrained(
        str(_model_dir()),
        trust_remote_code=True,
        local_files_only=True,
    )
    model.eval().to("cuda" if torch.cuda.is_available() else "cpu")
    return model


def _aligned_matrix(readings_by_type: dict[str, list[tuple[datetime, float]]]):
    import numpy as np

    all_times = sorted({t for rows in readings_by_type.values() for t, _ in rows})
    if not all_times:
        raise ValueError("No telemetry readings are available.")
    end = all_times[-1]
    start = end - timedelta(hours=1)
    grid = np.linspace(start.timestamp(), end.timestamp(), SEQUENCE_LENGTH)
    matrix = np.zeros((SEQUENCE_LENGTH, len(SENSOR_TYPES)), dtype=np.float32)

    for c, kind in enumerate(SENSOR_TYPES):
        rows = [(t.timestamp(), float(v)) for t, v in readings_by_type.get(kind, []) if start <= t <= end]
        if not rows:
            continue
        xs = np.asarray([x for x, _ in rows], dtype=np.float64)
        ys = np.asarray([y for _, y in rows], dtype=np.float32)
        if len(xs) == 1:
            matrix[:, c] = ys[0]
        else:
            order = np.argsort(xs)
            matrix[:, c] = np.interp(grid, xs[order], ys[order])

    mean = matrix.mean(axis=0, keepdims=True)
    std = matrix.std(axis=0, keepdims=True)
    return (matrix - mean) / (std + 1e-6)


def score_machine(db, machine_id: int) -> dict:
    import numpy as np
    import torch
    from .. import models

    rows = (
        db.query(models.SensorReading)
        .filter(models.SensorReading.machine_id == machine_id)
        .filter(models.SensorReading.reading_type.in_(SENSOR_TYPES))
        .order_by(models.SensorReading.recorded_at.desc(), models.SensorReading.id.desc())
        .limit(2000)
        .all()
    )
    by_type = {kind: [] for kind in SENSOR_TYPES}
    for r in reversed(rows):
        by_type[r.reading_type].append((r.recorded_at, r.value))

    samples = sum(bool(v) for v in by_type.values())
    if samples == 0:
        return {"available": False, "model": MODEL_NAME, "reason": "No supported telemetry yet."}

    missing = [kind for kind in SENSOR_TYPES if not by_type[kind]]
    if missing:
        return {
            "available": False,
            "model": MODEL_NAME,
            "reason": f"Waiting for telemetry channels: {', '.join(missing)}",
        }

    status = pretrained_status()
    if not status["configured"]:
        return {"available": False, **status}

    values = _aligned_matrix(by_type)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    with torch.no_grad():
        output = _load_model()(input_values=torch.from_numpy(values[None]).to(device))
    score = float(output.anomaly_scores.detach().float().cpu().numpy().mean())

    return {
        "available": True,
        "model": MODEL_NAME,
        "mode": "zero_shot_anomaly",
        "anomaly_score": score,
        "sequence_length": SEQUENCE_LENGTH,
        "channels": list(SENSOR_TYPES),
        "calibration_status": "pretrained_zero_shot",
        "warning": "Anomaly score is not a calibrated failure probability.",
    }
