# MAINTAIN AI bootstrap training — Google Colab

The first GPU training environment is Google Colab. Raw datasets stay outside GitHub.

## 1. Clone Lab and install

```bash
git clone -b Lab https://github.com/jadhavdurvesh/Maintain.ai.3.git
cd Maintain.ai.3
pip install -r training/requirements.txt
```

## 2. Put real datasets in /content/training-data

Expected layout:
- cmapss/train_FD001.txt (and other C-MAPSS files)
- ims/<run directories>/<measurement files>
- cwru/<mat files>
- paderborn/<mat files>

Follow each dataset's access, license and citation requirements.

## 3. Convert sources

```bash
PYTHONPATH=training/src python -m adapters.build_common --dataset cmapss --path /content/training-data/cmapss/train_FD001.txt --out /content/prepared/cmapss_FD001.parquet
PYTHONPATH=training/src python -m adapters.build_common --dataset ims --path /content/training-data/ims --out /content/prepared/ims.parquet
PYTHONPATH=training/src python -m adapters.build_common --dataset cwru --path /content/training-data/cwru --out /content/prepared/cwru.parquet
PYTHONPATH=training/src python -m adapters.build_common --dataset paderborn --path /content/training-data/paderborn --out /content/prepared/paderborn.parquet
```

The adapters preserve source semantics; they do not claim that incompatible
datasets are physically interchangeable.

## 4. Split by physical asset/run

```bash
PYTHONPATH=training/src python training/src/split_assets.py --input /content/prepared/cmapss_FD001.parquet --out-dir /content/splits/cmapss
```

This creates deterministic 70/15/15 train/validation/test splits by asset.

## 5. Build real temporal sequences

```bash
PYTHONPATH=training/src python training/src/build_sequences.py --input /content/splits/cmapss/train.parquet --out /content/sequences/cmapss_train.pt --sequence-length 24
PYTHONPATH=training/src python training/src/build_sequences.py --input /content/splits/cmapss/test.parquet --out /content/sequences/cmapss_test.pt --sequence-length 24
```

C-MAPSS RUL remains in cycles. IMS measurement steps remain source-native.
MAINTAIN AI's 24h/48h/7d targets will later come from real timestamps.

## 6. Train

```bash
PYTHONPATH=training/src python training/src/train.py --data /content/sequences/cmapss_train.pt --epochs 50 --batch-size 128 --out /content/artifacts/shared_temporal_v1.pt
```

The runner automatically uses CUDA when available.

## 7. Evaluate

```bash
PYTHONPATH=training/src python training/src/evaluate.py --data /content/sequences/cmapss_test.pt --model /content/artifacts/shared_temporal_v1.pt --out /content/artifacts/cmapss_test_metrics.json
```

The first report contains RUL MAE/RMSE. We will expand evaluation with
asset-level error, degradation-stage error and calibration before deployment.

## Interpretation

This bootstrap run tests whether the shared temporal encoder learns useful
degradation/RUL representations from real multivariate trajectories. It does
not prove 24h/48h/7d failure prediction for MAINTAIN AI's machine categories.
That requires verified category-specific failure data and, ultimately, real
MAINTAIN AI telemetry plus technician-confirmed outcomes.
