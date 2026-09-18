"""Build a normalized parquet file from a supported public PHM dataset."""
import argparse, json
from pathlib import Path
import pandas as pd
from . import cmapss, ims, cwru, paderborn

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--dataset",required=True)
    p.add_argument("--path",required=True)
    p.add_argument("--rul-path",default=None)
    p.add_argument("--out",required=True)
    a=p.parse_args()
    loaders={"cmapss":cmapss.load,"ims":ims.load,"cwru":cwru.load,"paderborn":paderborn.load}
    if a.dataset not in loaders:
        raise SystemExit(f"unknown dataset {a.dataset}")
    if a.dataset == "cmapss":
        df=loaders[a.dataset](a.path,rul_path=a.rul_path)
    else:
        df=loaders[a.dataset](a.path)
    Path(a.out).parent.mkdir(parents=True,exist_ok=True)
    df.to_parquet(a.out,index=False)
    print(json.dumps({
        "dataset":a.dataset,
        "rows":len(df),
        "assets":int(df.asset_id.nunique()) if len(df) else 0,
        "columns":list(df.columns)
    },indent=2))

if __name__=="__main__":
    main()
