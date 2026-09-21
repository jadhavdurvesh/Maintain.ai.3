"""Online degradation evidence built from the persistent machine baselines.

This is deliberately not a failure probability. It turns the four-signal online
learner into a time-ordered, explainable degradation timeline that can later be
used as features for a calibrated risk model once confirmed outcomes exist.
"""
from __future__ import annotations
import json
import math
from datetime import datetime, timedelta

from .. import models
from .online import score_machine

MAX_SNAPSHOTS = 500
SNAPSHOT_MIN_SECONDS = 60


def build_snapshot(db, machine_id: int, recorded_at: datetime | None = None) -> dict:
    now = recorded_at or datetime.utcnow()
    behaviour = score_machine(db, machine_id)
    signals = behaviour.get("signals", []) if behaviour.get("available") else []
    active = [s for s in signals if s.get("active")]
    max_anomaly = max((float(s.get("anomaly_score", 0)) for s in signals), default=0.0)
    correlation = float(behaviour.get("multi_sensor", {}).get("correlation_score", 0.0))

    # Degradation evidence weights persistent multi-sensor change, but never
    # presents the result as a probability of failure.
    score = min(1.0, 0.65 * max_anomaly + 0.35 * correlation)
    directions = [int(s.get("direction", 0)) for s in active if int(s.get("direction", 0)) != 0]
    trend = 0.0
    if directions:
        trend = min(1.0, abs(sum(directions)) / len(directions)) * score

    evidence = [
        {
            "reading_type": s["reading_type"],
            "anomaly_score": s["anomaly_score"],
            "direction": s["direction"],
            "ewma": s["ewma"],
            "baseline": s["mean"],
        }
        for s in sorted(active, key=lambda x: x["anomaly_score"], reverse=True)[:4]
    ]

    recent = (
        db.query(models.MLDegradationSnapshot)
        .filter_by(machine_id=machine_id)
        .order_by(models.MLDegradationSnapshot.recorded_at.desc())
        .first()
    )
    if recent and (now - recent.recorded_at).total_seconds() < SNAPSHOT_MIN_SECONDS:
        return {
            "available": True, "machine_id": machine_id, "recorded_at": recent.recorded_at.isoformat(),
            "degradation_score": round(recent.degradation_score, 4),
            "trend_score": round(recent.trend_score, 4),
            "active_signal_count": recent.active_signal_count,
            "evidence": json.loads(recent.evidence_json or "[]"),
            "source": recent.source,
        }

    snapshot = models.MLDegradationSnapshot(
        machine_id=machine_id,
        recorded_at=now,
        degradation_score=score,
        trend_score=trend,
        active_signal_count=len(active),
        evidence_json=json.dumps(evidence),
        source="online_behaviour",
    )
    db.add(snapshot)
    db.commit()

    # Keep the timeline bounded per machine without deleting telemetry/history.
    old_ids = [
        row[0] for row in (
            db.query(models.MLDegradationSnapshot.id)
            .filter_by(machine_id=machine_id)
            .order_by(models.MLDegradationSnapshot.recorded_at.desc())
            .offset(MAX_SNAPSHOTS)
            .all()
        )
    ]
    if old_ids:
        db.query(models.MLDegradationSnapshot).filter(models.MLDegradationSnapshot.id.in_(old_ids)).delete(synchronize_session=False)
        db.commit()

    return {
        "available": True, "machine_id": machine_id, "recorded_at": now.isoformat(),
        "degradation_score": round(score, 4), "trend_score": round(trend, 4),
        "active_signal_count": len(active), "evidence": evidence, "source": "online_behaviour",
    }


def get_timeline(db, machine_id: int, limit: int = 48) -> dict:
    limit = max(1, min(int(limit), 200))
    rows = (
        db.query(models.MLDegradationSnapshot)
        .filter_by(machine_id=machine_id)
        .order_by(models.MLDegradationSnapshot.recorded_at.desc())
        .limit(limit)
        .all()
    )
    return {
        "machine_id": machine_id,
        "points": [
            {
                "recorded_at": row.recorded_at.isoformat(),
                "degradation_score": round(row.degradation_score, 4),
                "trend_score": round(row.trend_score, 4),
                "active_signal_count": row.active_signal_count,
                "evidence": json.loads(row.evidence_json or "[]"),
            }
            for row in reversed(rows)
        ],
    }
