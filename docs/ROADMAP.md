# MAINTAIN AI — Future Roadmap

## Next implementation

### A. AI Monitoring / Model Lab
- Dedicated view for pretrained model availability.
- Latest anomaly/degradation signals per machine.
- Forecast availability and inference health.
- Telemetry coverage and data-quality warnings.
- 24h/48h/7d/30d label coverage.
- Model/version metadata and last inference.
- No undefined or misleading AI confidence score.

### B. Unified temporal evidence timeline
Create one chronological machine evidence stream containing telemetry behaviour, online anomaly, TimeRadar anomaly, forecasts, degradation trend, faults, maintenance, work orders and technician outcomes.

This becomes the canonical debugging and evaluation surface.

### C. Data quality layer
Detect missing intervals, duplicate timestamps, impossible values, sensor flatlining, unit changes, clock drift, device disconnects, insufficient history and inconsistent machine category.

Model outputs should show when input quality is insufficient.

## Real predictive-risk model

Only train this after enough independent assets and confirmed outcomes exist.

Target architecture:

Multivariate temporal encoder -> shared degradation representation -> category-conditioned adapters/heads -> four risk heads (24h, 48h, 7d, 30d).

Use the existing machine category field for routing; do not create another machine-type field.

Training requirements:
- asset-level train/validation/test splits
- train-only normalization
- strict point-in-time features
- class-imbalance handling
- hard normal negatives
- event-based lead-time evaluation
- probability calibration
- independent held-out assets
- versioned preprocessing/model artifacts

## Evaluation

Track PR-AUC, ROC-AUC, precision, recall at an explicit false-alarm budget, calibration error/Brier score, warning lead time, failure detection before each horizon, false alarms per machine-month, missed failures, alert persistence and inference latency.

Do not use accuracy alone for imbalanced failure data.

## RUL

Add RUL only for asset families with meaningful run-to-failure trajectories and known endpoints. Otherwise prefer a risk/evidence formulation rather than an invented RUL number.

## Closed learning loop

Prediction -> alert -> maintenance action -> technician confirmation -> outcome store -> retraining/recalibration -> new model version.

Old model versions and their evaluation results should remain reproducible.

## Deployment

The core Vercel/API path should remain lightweight. Heavy pretrained or future temporal inference should be isolated into a dedicated ML worker/service when package size, memory, runtime or GPU needs make serverless execution unsuitable.

Target:

Browser/Desktop -> FastAPI -> operational DB
                         -> ML inference worker
                            -> TimeRadar / Chronos-2 / Timer / future risk model

## Longer-term capabilities

- OPC-UA/Modbus/historian connectors
- technician mobile workflow
- model drift detection
- model registry
- component-level risk
- fleet failure clustering
- maintenance optimization
- spare-parts demand forecasting
- cost-of-failure analysis
- maintenance scheduling optimization

## Definition of success

Good telemetry -> trustworthy temporal representation -> explainable degradation evidence -> validated future-risk model -> calibrated probabilities -> useful warning lead time -> technician-confirmed outcomes -> measurable maintenance improvement.

A model is promoted because it improves validated operational metrics, not because it is larger or newer.