"""Single orchestration layer for live MAINTAIN AI temporal intelligence.

Telemetry ingestion updates the lightweight online learner synchronously. Heavy
pretrained inference remains optional and is exposed through a separate API so
a model download/GPU operation can never block telemetry ingestion.
"""
from .degradation import build_snapshot


def process_telemetry(db, machine_id: int, recorded_at=None):
    return build_snapshot(db, machine_id, recorded_at)
