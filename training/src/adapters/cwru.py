"""CWRU MATLAB bearing-data adapter.
Each MATLAB file contains DE/FE/BA vibration arrays and RPM metadata.
This adapter creates one temporal observation per file.
"""
from pathlib import Path
import re
import numpy as np
import pandas as pd
from scipy.io import loadmat
def _one(path):
    mat=loadmat(path,squeeze_me=True)
    row={}
    for key,val in mat.items():
        if key.startswith("__"): continue
        a=np.asarray(val).squeeze()
        if a.ndim==0:
            try: row[key.lower()]=float(a)
            except Exception: pass
        elif a.size>10 and np.issubdtype(a.dtype,np.number):
            x=a.astype(float); row[f"{key.lower()}_rms"]=float(np.sqrt(np.mean(x*x))); row[f"{key.lower()}_std"]=float(np.std(x)); row[f"{key.lower()}_max"]=float(np.max(np.abs(x)))
    return row
def _fault(path):
    name=path.stem.upper()
    if name.startswith("IR"): return "inner_race"
    if name.startswith("OR"): return "outer_race"
    if name.startswith("B"): return "ball"
    return None
def load(root):
    rows=[]
    for i,path in enumerate(sorted(Path(root).rglob("*.mat"))):
        try:r=_one(path)
        except Exception:continue
        r.update(asset_id=f"cwru_{i}",timestamp=0.0,category="induction_motor",source="cwru_bearing",failure=bool(_fault(path)),failure_type=_fault(path))
        rows.append(r)
    return pd.DataFrame(rows)
