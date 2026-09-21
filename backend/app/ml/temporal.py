"""MAINTAIN AI V1.1 shared temporal bootstrap artifact loader.

V1 is trained on NASA C-MAPSS FD001-FD004 for bootstrap RUL representation.
It is not calibrated for MAINTAIN AI industrial sensor semantics. The 24h,
48h and 7d risk heads exist architecturally but were not trained in V1.1.

The checkpoint is stored as a base64 text blob because the repository workflow
uses text-safe GitHub Contents/Git Data operations.
"""
from __future__ import annotations

import base64
import io
import json
from functools import lru_cache
from pathlib import Path

ARTIFACT_DIR = Path(__file__).resolve().parent / "artifacts" / "maintain_ai_shared_temporal_v1_1"
MODEL_B64_PATH = ARTIFACT_DIR / "model.pt.b64"
METADATA_PATH = ARTIFACT_DIR / "model_metadata.json"
METRICS_PATH = ARTIFACT_DIR / "metrics.json"

CATEGORIES = ("induction_motor", "pump", "compressor", "conveyor", "other")
CATEGORY_TO_ID = {name: index for index, name in enumerate(CATEGORIES)}
SEQUENCE_LENGTH = 24
INPUT_CHANNELS = 24
MODEL_VERSION = "shared-temporal-v1.1"


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _checkpoint_bytes() -> bytes:
    with MODEL_B64_PATH.open("r", encoding="ascii") as handle:
        return base64.b64decode(handle.read())


def artifact_status() -> dict:
    metadata = _load_json(METADATA_PATH) if METADATA_PATH.exists() else {}
    metrics = _load_json(METRICS_PATH) if METRICS_PATH.exists() else {}
    torch_available = False
    loadable = False
    reason = None

    try:
        import torch  # noqa: F401
        torch_available = True
    except ImportError:
        reason = "PyTorch is not installed in this runtime."

    if torch_available and MODEL_B64_PATH.exists():
        try:
            _load_model()
            loadable = True
        except Exception as exc:
            reason = f"Model artifact could not be loaded: {type(exc).__name__}: {exc}"

    return {
        "available": loadable,
        "artifact_present": MODEL_B64_PATH.exists(),
        "pytorch_available": torch_available,
        "model_version": metadata.get("model_version", MODEL_VERSION),
        "architecture": metadata.get("architecture"),
        "input_channels": metadata.get("input_channels", INPUT_CHANNELS),
        "sequence_length": metadata.get("sequence_length", SEQUENCE_LENGTH),
        "categories": metadata.get("categories", list(CATEGORIES)),
        "training_objective": metadata.get("training_objective"),
        "risk_outputs": metadata.get("risk_outputs", []),
        "risk_status": metadata.get("risk_status"),
        "bootstrap_datasets": metadata.get("bootstrap_datasets", []),
        "bootstrap_metrics": metrics,
        "reason": reason,
    }


def _build_model():
    from torch import nn

    class SharedTemporalModel(nn.Module):
        def __init__(self):
            super().__init__()
            self.temporal_conv = nn.Sequential(
                nn.Conv1d(INPUT_CHANNELS, 64, kernel_size=5, padding=2),
                nn.BatchNorm1d(64),
                nn.GELU(),
                nn.Conv1d(64, 96, kernel_size=5, padding=2),
                nn.BatchNorm1d(96),
                nn.GELU(),
            )
            self.gru = nn.GRU(96, 128, num_layers=2, batch_first=True)
            self.category_embedding = nn.Embedding(len(CATEGORIES), 16)
            self.fusion = nn.Sequential(nn.Linear(144, 128), nn.GELU())
            self.risk_head = nn.Linear(128, 3)
            self.rul_head = nn.Sequential(nn.Linear(128, 64), nn.GELU(), nn.Linear(64, 1))

        def forward(self, x, category_id):
            x = self.temporal_conv(x.transpose(1, 2)).transpose(1, 2)
            temporal, _ = self.gru(x)
            last = temporal[:, -1, :]
            category = self.category_embedding(category_id)
            fused = self.fusion(torch.cat([last, category], dim=1))
            return self.risk_head(fused), self.rul_head(fused).squeeze(-1)

    return SharedTemporalModel()


@lru_cache(maxsize=1)
def _load_model():
    import torch

    checkpoint = torch.load(io.BytesIO(_checkpoint_bytes()), map_location="cpu", weights_only=False)
    model = _build_model()
    model.load_state_dict(checkpoint["model_state_dict"], strict=True)
    model.eval()
    return model


def predict_normalized(sequence, category: str) -> dict:
    import numpy as np
    import torch

    category = (category or "other").strip().lower().replace(" ", "_")
    if category not in CATEGORY_TO_ID:
        raise ValueError(f"Unsupported machine category: {category}")

    values = np.asarray(sequence, dtype=np.float32)
    if values.shape != (SEQUENCE_LENGTH, INPUT_CHANNELS):
        raise ValueError(
            f"Expected sequence shape ({SEQUENCE_LENGTH}, {INPUT_CHANNELS}), got {tuple(values.shape)}"
        )

    with torch.no_grad():
        risk_logits, rul = _load_model()(
            torch.from_numpy(values).unsqueeze(0),
            torch.tensor([CATEGORY_TO_ID[category]], dtype=torch.long),
        )

    return {
        "model_version": MODEL_VERSION,
        "category": category,
        "rul": float(rul.item()),
        "risk_outputs": None,
        "risk_status": "Not trained yet",
        "risk_logits": risk_logits.squeeze(0).tolist(),
        "calibration_status": "bootstrap_only",
    }
