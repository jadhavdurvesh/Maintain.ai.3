"""NASA/IMS bearing adapter for measurement text files.

IMS files are sampled vibration snapshots rather than low-rate telemetry.
We reduce each snapshot to robust statistical features, preserving the
measurement order as the temporal axis. Each run/directory is one asset.
"""
from pathlib import Path
import numpy as np
import pandas as pd
def _features(path):
    x=pd.read_csv(path,sep=r"\s+",header=None,engine="python").apply(pd.to_numeric,errors="coerce").dropna(axis=1,how="all").to_numpy()
    feats={}
    for j in range(x.shape[1]):
        v=x[:,j].astype(float); feats[f"vibration_{j+1}_rms"]=float(np.sqrt(np.mean(v*v))); feats[f"vibration_{j+1}_std"]=float(np.std(v)); feats[f"vibration_{j+1}_max"]=float(np.max(np.abs(v)))
    return feats
def load(root):
    root=Path(root); rows=[]
    for run in sorted(p for p in root.iterdir() if p.is_dir()):
        for i,path in enumerate(sorted(p for p in run.iterdir() if p.is_file())):
            try: f=_features(path)
            except Exception: continue
            f.update(asset_id=f"ims_{run.name}",timestamp=float(i),category="induction_motor",source="ims_bearings")
            rows.append(f)
    df=pd.DataFrame(rows)
    if df.empty:return df
    last=df.groupby("asset_id")["timestamp"].transform("max"); df["rul_hours"]=last-df["timestamp"]
    return df
