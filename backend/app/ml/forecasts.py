"""Optional pretrained forecasting adapters.

These models are used only for expected-signal forecasting. They do not emit
failure probabilities and they do not train. The application can compare the
forecast with live telemetry later to strengthen degradation evidence.
"""
from __future__ import annotations

import os
from functools import lru_cache


def _enabled():
    return os.getenv("MAINTAIN_PRETRAINED_FORECASTS", "0").strip().lower() in {"1", "true", "yes", "on"}


def forecast_status():
    if not _enabled():
        return {"enabled": False, "models": ["Timer", "Chronos-2"], "reason": "Forecast models are optional and disabled by default."}
    available = {}
    for name, module_name in (("Timer", "transformers"), ("Chronos-2", "chronos")):
        try:
            __import__(module_name)
            available[name] = True
        except ImportError:
            available[name] = False
    return {"enabled": True, "models": available, "mode": "zero_shot_forecasting"}


@lru_cache(maxsize=1)
def _chronos():
    from chronos import Chronos2Pipeline
    import torch
    return Chronos2Pipeline.from_pretrained(
        os.getenv("MAINTAIN_CHRONOS_MODEL", "amazon/chronos-2"),
        device_map="cuda" if torch.cuda.is_available() else "cpu",
    )


def forecast_signal(values: list[float], horizon: int = 12):
    if not _enabled():
        return {"available": False, "reason": "Forecast models are disabled."}
    clean = [float(v) for v in values if v is not None]
    if len(clean) < 32:
        return {"available": False, "reason": "At least 32 recent samples are required for forecasting."}
    try:
        import torch
        pipeline = _chronos()
        forecast = pipeline.predict(torch.tensor(clean[-512:], dtype=torch.float32), prediction_length=horizon)
        arr = forecast.detach().float().cpu().numpy()
        median = arr[0, arr.shape[1] // 2].tolist() if arr.ndim == 3 else arr.reshape(-1).tolist()
        return {"available": True, "model": "Chronos-2", "forecast": median, "horizon": horizon}
    except Exception as exc:
        return {"available": False, "model": "Chronos-2", "reason": f"Forecast inference failed: {exc}"}
