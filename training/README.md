# MAINTAIN AI predictive-maintenance training

## Where training runs

The production FastAPI/Vercel application is **not** the training machine.
Training runs offline on a GPU environment (Google Colab GPU for the first
training cycle; a dedicated GPU VM can replace it later). The repository holds
the reproducible code/config, while downloaded datasets and model checkpoints
stay outside Git.

## Initial datasets

1. **IMS Bearings (University of Cincinnati / NASA PCoE)** — run-to-failure
   rotating-bearing degradation. Use this for temporal degradation/RUL learning
   and map it to rotating-equipment/bearing subsystem context, not as proof that
   every machine category has the same failure physics.
2. **Paderborn Bearing DataCenter** — motor-current + vibration with speed,
   torque, radial load and temperature; includes healthy, artificial-damage and
   accelerated-lifetime real-damage bearing experiments. Use for induction-motor
   bearing condition representation.
3. **CWRU Bearing Data Center** — documented motor bearing fault experiments.
   Use for bearing-fault representation/diagnostic pretraining, not as a
   run-to-failure RUL source.
4. **NASA C-MAPSS / N-CMAPSS** — multivariate run-to-failure engine trajectories.
   Use as generic temporal-prognostics pretraining/RUL validation. Do **not**
   label this as pump, compressor, motor or conveyor data.
5. **Pump dataset** — the Crompton Greaves CG-IPM-15 dataset can be used as
   pump-specific supplemental data when its source/license is verified before
   commercial use. It is synthetic, so it is not treated as equivalent to
   real industrial pump telemetry.

## What the first model learns

The first model is a **single shared temporal model**. It learns:

- temporal sensor representations;
- degradation/anomaly representation;
- category embedding/context;
- future failure-risk heads (24h/48h/7d) where labels exist;
- optional RUL head where true run-to-failure trajectories exist.

Category-specific routing/heads are trained only where the dataset actually
contains that category's evidence. We do not fabricate compressor/conveyor
failure labels from unrelated datasets.

## Training flow

raw public datasets
 -> dataset-specific adapters
 -> common timestamped telemetry schema
 -> per-asset temporal windows
 -> leakage-safe train/validation/test split by asset
 -> shared temporal encoder + category context
 -> multi-task prediction heads
 -> calibration/evaluation
 -> model artifact
 -> MAINTAIN AI inference service

## Important evaluation rule

Never split adjacent windows from the same asset randomly across train/test.
The split is by asset/run so the model cannot memorize one machine's trajectory.

## Later MAINTAIN AI data

Once real devices produce enough history, technician-confirmed faults,
component replacements and maintenance outcomes become the highest-value
fine-tuning/calibration data. The public datasets bootstrap the model; they do
not replace MAINTAIN AI's own evidence.
