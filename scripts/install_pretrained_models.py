#!/usr/bin/env python3
"""Install the pretrained TimeRadar checkpoint for local/desktop inference.

This downloads the public TimeRadar repository and copies its bundled
pretrained Hugging Face checkpoint into the MAINTAIN AI artifact directory.
No model training is performed.
"""
from __future__ import annotations

import shutil
import subprocess
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "backend" / "app" / "ml" / "artifacts" / "pretrained" / "TimeRadar"
TMP = ROOT / ".cache" / "timeradar"

REPO = "https://github.com/mala-lab/TimeRadar.git"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--with-forecasts", action="store_true", help="also cache Timer and Chronos-2 checkpoints")
    args = parser.parse_args()
    TMP.parent.mkdir(parents=True, exist_ok=True)
    if TMP.exists():
        shutil.rmtree(TMP)

    print("Downloading TimeRadar pretrained model...")
    subprocess.run(
        ["git", "clone", "--depth", "1", REPO, str(TMP)],
        check=True,
    )

    source = TMP / "TimeRadar"
    if not source.exists():
        raise SystemExit(f"Expected pretrained checkpoint directory was not found: {source}")

    DEST.parent.mkdir(parents=True, exist_ok=True)
    if DEST.exists():
        shutil.rmtree(DEST)
    shutil.copytree(source, DEST)

    shutil.rmtree(TMP, ignore_errors=True)
    print(f"Installed TimeRadar at: {DEST}")
    if args.with_forecasts:
        print("Caching Timer and Chronos-2 pretrained checkpoints...")
        subprocess.run(["python3", "-c", "from transformers import AutoModelForCausalLM; AutoModelForCausalLM.from_pretrained('thuml/timer-base-84m', trust_remote_code=True)"], check=True)
        subprocess.run(["python3", "-c", "from chronos import Chronos2Pipeline; Chronos2Pipeline.from_pretrained('amazon/chronos-2')"], check=True)
    print("No training was performed.")


if __name__ == "__main__":
    main()
