"""Paderborn .mat adapter.
Paderborn files encode operating condition and bearing identity in names such
as N15_M07_F10_KA01_1.mat. Arrays are reduced to window statistics.
"""
from pathlib import Path
import re
import numpy as np
import pandas as pd
from scipy.io import loadmat
def _one(path):
    mat=loadmat(path,squeeze_me=True); row={}
    for key,val in mat.items():
        if key.startswith("__"):continue
        a=np.asarray(val).squeeze()
        if a.ndim==0:
            try:row[key.lower()]=float(a)
            except Exception:pass
        elif a.size>10 and np.issubdtype(a.dtype,np.number):
            x=a.astype(float); row[f"{key.lower()}_rms"]=float(np.sqrt(np.mean(x*x))); row[f"{key.lower()}_std"]=float(np.std(x)); row[f"{key.lower()}_max"]=float(np.max(np.abs(x)))
    return row
def load(root):
    rows=[]
    for i,path in enumerate(sorted(Path(root).rglob("*.mat"))):
        m=re.search(r"_(K[A-Z]\d\d)_",path.stem.upper())
        bearing=m.group(1) if m else path.stem
        r=_one(path); r.update(asset_id=f"paderborn_{bearing}",timestamp=float(i),category="induction_motor",source="paderborn_bearing")
        r["failure"]=not bearing.startswith("K0") and bearing[:2] not in {"KA","KI","KB"} if False else False
        rows.append(r)
    return pd.DataFrame(rows)
