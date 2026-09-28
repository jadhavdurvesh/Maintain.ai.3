# Automatic Forecasting

MAINTAIN AI uses `Chronos-Bolt-Tiny` as the default production time-series forecaster because the dedicated Render ML service is resource-constrained.

## Lifecycle

1. A new sensor reading is committed with `source="sensor"`.
2. The database session commit listener schedules the forecast coordinator.
3. The coordinator verifies the signal is enabled, at least 32 samples exist, and the machine is active.
4. A five-minute cadence is applied by default so frequent telemetry does not cause a model call for every reading.
5. The exact input ending at the latest reading is used as the forecast identity. Repeating the same input returns the saved run instead of creating another inference.
6. The forecast is persisted in `ml_forecast_runs`.
7. If telemetry stops, no new telemetry event means no automatic forecast invocation.

## Environment variables

- `ML_AUTO_FORECASTS=1` enables automatic forecasting (default on).
- `ML_FORECAST_MODEL=chronos-bolt-tiny` selects the default model.
- `ML_FORECAST_HORIZON=12` sets the automatic horizon.
- `ML_FORECAST_INTERVAL_SECONDS=300` sets the minimum automatic cadence.
- `ML_AUTO_FORECAST_SIGNALS=temperature,vibration,current,load,humidity` controls signals eligible for automatic forecasting.
- `MAINTAIN_ML_SERVICE_URL` selects the dedicated ML service.
- `MAINTAIN_ML_API_KEY` optionally authenticates backend-to-ML requests.

Manual `Run now` requests bypass the cadence but still use the same durable/idempotent forecast record model.

## Time-series models

- **Chronos-Bolt-Tiny:** default production forecast path through `Maintain-AI-ML`.
- **Timer:** secondary time-series model available through the backend Timer adapter; it is not the automatic default.

Neither model is a calibrated failure-probability model. Forecasts are evidence about future sensor values and must be interpreted with telemetry, degradation, thresholds, maintenance history, and technician outcomes.
