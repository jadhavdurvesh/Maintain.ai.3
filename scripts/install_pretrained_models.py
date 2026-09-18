#!/usr/bin/env python3
"""Install the pretrained TimeRadar checkpoint for local/desktop inference.

This downloads the public TimeRadar repository and copies its bundled
pretrained Hugging Face checkpoint into the MAINTAIN AI artifact directory.
No model training is performed.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "backend" / "app" / "ml" / "artifacts" / "pretrained" / "TimeRadar"
TMP = ROOT / ".cache" / "timeradar"

REPO = "https://github.com/mala-lab/TimeRadar.git"


def main():
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
    print("No training was performed.")


if __name__ == "__main__":
    main()
