"""Optional Timer zero-shot forecaster from the official Large-Time-Series-Model checkpoint."""
from __future__ import annotations

import os
from functools import lru_cache


@lru_cache(maxsize=1)
def _timer():
    from transformers import AutoModelForCausalLM
    import torch
    model = AutoModelForCausalLM.from_pretrained(
        os.getenv("MAINTAIN_TIMER_MODEL", "thuml/timer-base-84m"),
        trust_remote_code=True,
    )
    return model.to("cuda" if torch.cuda.is_available() else "cpu").eval()


def timer_status():
    enabled = os.getenv("MAINTAIN_PRETRAINED_FORECASTS", "0").strip().lower() in {"1", "true", "yes", "on"}
    return {"enabled": enabled, "model": "Timer", "checkpoint": os.getenv("MAINTAIN_TIMER_MODEL", "thuml/timer-base-84m")}


def forecast(values: list[float], horizon: int = 12):
    if not timer_status()["enabled"]:
        return {"available": False, **timer_status(), "reason": "Forecast models are disabled."}
    if len(values) < 32:
        return {"available": False, "model": "Timer", "reason": "At least 32 recent samples are required."}
    try:
        import torch
        import numpy as np
        x = np.asarray(values[-2880:], dtype=np.float32)
        mean, std = float(x.mean()), float(x.std() or 1.0)
        seq = torch.tensor(((x - mean) / std)[None], dtype=torch.float32)
        device = "cuda" if torch.cuda.is_available() else "cpu"
        output = _timer().generate(seq.to(device), max_new_tokens=horizon)
        pred = output[0, -horizon:].detach().float().cpu().numpy() * std + mean
        return {"available": True, "model": "Timer", "forecast": pred.tolist(), "horizon": horizon}
    except Exception as exc:
        return {"available": False, "model": "Timer", "reason": f"Forecast inference failed: {exc}"}
