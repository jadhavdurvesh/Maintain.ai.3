# MAINTAIN AI V1 model artifact

The V1 checkpoint supplied with this project is the uploaded
`maintain_ai_shared_temporal_v1.zip`.

For deployment, extract its `model.pt` and place it at:

`backend/app/ml/artifacts/maintain_ai_shared_temporal_v1/model.pt.b64`

The repository integration intentionally keeps the checkpoint out of the
normal source-text path until the exact binary can be transferred without
alteration. The backend loader also accepts the text-safe base64 representation
and exposes `GET /api/analytics/temporal-model-status`.

V1 is bootstrap-only:
- objective: RUL on NASA C-MAPSS FD001-FD004
- sequence: 24 C-MAPSS cycles, not 24 hours
- 24h/48h/7d risk heads: not trained
- not calibrated for MAINTAIN AI industrial sensor semantics

Do not use the V1 RUL output as an industrial machine RUL estimate until a
training-matched sensor adapter and category-relevant calibration are added.
