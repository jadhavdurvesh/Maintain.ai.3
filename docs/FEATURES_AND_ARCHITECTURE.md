# MAINTAIN AI — What We Built & How It Works

This is the living technical map of the MAINTAIN AI system on the Lab branch. It records implemented features, how data moves through them, model limitations, and the path to the future predictive-maintenance model.

## 1. Product architecture

Users -> React/Vite web UI or Electron desktop client -> FastAPI -> SQLAlchemy/SQLite -> operational data + ML services.

Telemetry enters through REST/device ingestion, is processed by the online intelligence path, stored as history, and can be streamed to the Machine Detail page over WebSocket.

## 2. Fleet and machine management

- Machine records with category, operating hours, health and criticality.
- Categories currently include induction_motor, pump, conveyor, compressor and other.
- Components and machine history.
- Archive-based removal so historical records are preserved.

## 3. Maintenance operations

- Maintenance planning and history.
- Work-order workflow: Pending -> In Progress -> Completed.
- Completion requires resolution notes.
- Completing work can automatically capture an ML outcome record.
- Fault log supports explicit technician outcome feedback: outcome, component, root cause, downtime, corrective action, false-alarm flag and notes.

This creates the feedback loop: telemetry -> signal -> alert/work order -> technician outcome -> future training data.

## 4. Live telemetry and WebSocket

ESP32 or another compatible device can send readings using a device key. The example firmware is firmware/esp32_example.ino.

Processing flow:

Reading -> authentication/ingestion -> online behaviour -> anomaly evidence -> degradation snapshot -> safety evaluation -> WebSocket event.

The live UI keeps only a compact recent window for responsiveness. Database history is retained.

## 5. Online anomaly intelligence

backend/app/ml/online.py maintains recent behaviour for temperature, vibration, current and load using running statistics/EWMA-style tracking, persistence and cross-sensor evidence.

Important: an anomaly score is not a failure probability. An unusual reading can be benign, and failure can occur without a large anomaly on the monitored channels.

## 6. Degradation timeline

MLDegradationSnapshot stores explainable degradation evidence derived from online behaviour. The timeline includes anomaly contribution, correlation contribution, trend and evidence text.

The Machine Detail page shows this history so an operator can see why concern increased over time.

## 7. Pretrained temporal models

TimeRadar is integrated as an optional zero-shot anomaly detector. MAINTAIN AI does not train or modify its pretrained weights.

Local artifact location: backend/app/ml/artifacts/pretrained/TimeRadar/

TimeRadar flow: recent aligned telemetry -> temporal window -> normalization -> pretrained inference -> anomaly-oriented signal -> analytics API -> Machine Detail.

Chronos-2 and Timer are optional zero-shot forecasting adapters. They forecast future signal values; they do not directly output calibrated machine-failure probabilities.

Forecast support is enabled with MAINTAIN_PRETRAINED_FORECASTS=1.

## 8. Temporal labels and risk readiness

The project has a future-label foundation for 24h, 48h, 7d and 30d horizons. A sample is only labelled when the complete future horizon is observable, preventing end-of-dataset leakage.

Fleet risk-readiness reports complete labels and positive/negative outcome counts. This is a data-readiness measurement, not a fabricated prediction.

## 9. Bootstrap ML experiments

NASA C-MAPSS was used for temporal degradation/RUL bootstrap work. V1.1 used 24 channels, 24-cycle sequences, asset-aware splits, train-only normalization and official test evaluation.

V1.1 results: internal test MAE 34.2220, RMSE 50.8709; official NASA test MAE 25.1171, RMSE 36.3652. These are C-MAPSS benchmark results, not production claims for industrial machines.

Industrial V1.3 used MetroPT-3 compressor data and CG-IPM-15 pump data. The experiment exposed insufficient normal negatives, limited independent pump episodes and invalid event-window evaluation for some horizons. The 24h/48h risk discrimination was close to random. That result is intentionally treated as evidence that the real risk model needs better data and evaluation.

## 10. Existing Random Forest baseline

A lightweight scikit-learn Random Forest remains available as a machine-level baseline. It uses operational/history features and can be retrained from Reports.

It is not the final multivariate temporal failure-risk model.

## 11. Safety

Machine safety policies, warning/shutdown thresholds, safety events, shutdown command paths and firmware relay/contactor handling are implemented.

MAINTAIN AI is supervisory software and must not be the sole industrial safety protection. Hardwired safety, PLC/interlocks and emergency-stop systems remain necessary.

## 12. AI maintenance assistant

The AI Assistant is separate from the temporal predictive layer. It can ask clarifying questions, distinguish confirmed/likely/possible/insufficient evidence, provide inspection procedures and optionally use Gemini.

Gemini is advisory and optional. The predictive-maintenance architecture does not depend on an LLM.

## 13. Reports and exports

Reports cover machines, work orders, maintenance, faults, alerts, sensor readings, components, safety settings/events, spare parts and notifications. Individual CSV exports and a complete ZIP archive are available, plus PDF/Excel paths and a Gemini-assisted detailed PDF.

## 14. Authentication

Authentication can be enabled with REQUIRE_AUTH=true. JWT sessions, organization scoping and Admin/Technician/Viewer roles are supported.

## 15. Desktop

The Electron client is a cloud-connected installable client targeting Windows, macOS and Linux. It connects to the hosted backend rather than pretending that a local desktop package is itself a production server.

See DESKTOP.md for packaging.

## 16. Reliability/performance work

- Best-effort database startup and reduced startup blocking.
- Protected telemetry-window materialization.
- Corrected telemetry-window uniqueness.
- Machine Detail no longer depends on a large combined endpoint.
- Independent Machine Detail requests can load in parallel.
- API timeout handling.
- WebSocket live readings.
- Compact live history while retaining database history.

## 17. Current status

| Area | Status |
| --- | --- |
| Fleet/machines | Built |
| Maintenance/work orders | Built |
| Faults + technician outcomes | Built |
| REST telemetry | Built |
| WebSocket live telemetry | Built |
| Online anomaly engine | Built |
| Degradation timeline | Built |
| TimeRadar zero-shot anomaly | Optional/integrated |
| Chronos-2 forecasting | Optional/integrated |
| Timer forecasting | Optional/integrated |
| 24h/48h/7d/30d label foundation | Built |
| Fleet risk readiness | Built |
| Calibrated future failure probability | Not yet |
| Production RUL | Not yet |
| Safety supervision | Built |
| Reports/exports | Built |
| Desktop client | Built |
| AI assistant | Built |

## 18. End-to-end intelligence target

Sensors -> telemetry history -> online behaviour -> anomaly evidence -> degradation timeline -> pretrained temporal signals/forecasts -> technician outcomes -> validated supervised risk model -> calibrated 24h/48h/7d/30d probabilities.

The key design rule is that evidence comes before a claimed probability. We do not label an anomaly score as a failure percentage.