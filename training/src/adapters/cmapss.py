"""NASA C-MAPSS text adapter.

Supports the original NASA C-MAPSS FD001-FD004 train/test files.
Train trajectories run to failure, so RUL is computed from each engine's
last observed training cycle. Test trajectories are truncated before failure;
NASA supplies one RUL target per test engine in RUL_FDxxx.txt. For test data,
the target is attached only to the final observed cycle so evaluation matches
the published C-MAPSS protocol.
"""
from pathlib import Path
import pandas as pd

COLS=["unit_id","cycle","op_1","op_2","op_3"]+[f"sensor_{i}" for i in range(1,22)]

def _subset_from_path(path):
    name=Path(path).name.upper()
    for subset in ("FD001","FD002","FD003","FD004"):
        if subset in name:
            return subset
    raise ValueError(f"Could not infer C-MAPSS subset from filename: {path}")

def load(path, rul_path=None):
    path=Path(path)
    subset=_subset_from_path(path)
    is_test=path.name.lower().startswith("test_")

    df=pd.read_csv(path,sep=r"\s+",header=None,names=COLS,engine="python")
    df["subset"]=subset
    df["asset_id"]=df["unit_id"].map(lambda x:f"cmapss_{subset}_{int(x)}")
    df["timestamp"]=df["cycle"].astype(float)
    df["category"]="other"
    df["source"]="nasa_cmapss"

    if not is_test:
        df["rul_steps"]=df.groupby("unit_id")["cycle"].transform("max")-df["cycle"]
    else:
        if rul_path is None:
            raise ValueError(f"{path.name} is a test file; provide --rul-path RUL_{subset}.txt")
        rul=pd.read_csv(rul_path,sep=r"\s+",header=None,names=["rul_steps"])
        if len(rul) != df["unit_id"].nunique():
            raise ValueError(
                f"{Path(rul_path).name} has {len(rul)} targets but {path.name} has "
                f"{df['unit_id'].nunique()} test assets"
            )
        targets={i+1:float(v) for i,v in enumerate(rul["rul_steps"])}
        last_cycle=df.groupby("unit_id")["cycle"].transform("max")
        df["rul_steps"]=float("nan")
        df.loc[df["cycle"].eq(last_cycle),"rul_steps"]=df.loc[
            df["cycle"].eq(last_cycle),"unit_id"
        ].map(targets)

    return df
