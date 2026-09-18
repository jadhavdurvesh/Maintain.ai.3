"""Validate downloaded PHM data and create a reproducible manifest.

Raw datasets stay outside Git because of size/licensing. Dataset-specific
parsers will convert each source into the common training representation.
"""
import argparse, hashlib, json
from pathlib import Path
def sha256(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024), b""): h.update(chunk)
    return h.hexdigest()
def main():
    from backend.app.ml.public_datasets import DATASET_REGISTRY
    p=argparse.ArgumentParser()
    p.add_argument("--data-dir",default="./training-data")
    p.add_argument("--dataset",required=True,choices=sorted(DATASET_REGISTRY))
    a=p.parse_args()
    spec=DATASET_REGISTRY[a.dataset]; root=Path(a.data_dir)/a.dataset
    files=[x for x in root.rglob("*") if x.is_file() and x.name!="manifest.json"]
    if not files: raise SystemExit(f"No raw files found in {root}. Download the registered source first.")
    manifest={"dataset":a.dataset,"category":spec["category"],"role":spec["role"],"signals":list(spec["signals"]),"failure_target":spec["failure_target"],"source":spec["source"],"source_url":spec["source_url"],"files":[{"path":str(x.relative_to(root)),"sha256":sha256(x),"bytes":x.stat().st_size} for x in files]}
    (root/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    print(json.dumps(manifest,indent=2))
if __name__=="__main__": main()
