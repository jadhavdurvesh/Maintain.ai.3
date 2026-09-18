"""Normalize adapter outputs into fixed 28-channel tensors.

Channels 0-6 are physical signals. Channels 7-27 are generic source sensors.
A separate availability mask is produced so missing sensors are never treated
as real zero measurements.
"""
import numpy as np
PHYSICAL=("temperature","vibration","current","load","speed","pressure","flow")
def to_vector(row):
    x=np.full(28,np.nan,dtype=np.float32); m=np.zeros(28,dtype=np.float32)
    for i,name in enumerate(PHYSICAL):
        if name in row and row[name] is not None:
            try:x[i]=float(row[name]);m[i]=1
            except (TypeError,ValueError):pass
    for i in range(21):
        name=f"sensor_{i+1}"
        if name in row and row[name] is not None:
            try:x[7+i]=float(row[name]);m[7+i]=1
            except (TypeError,ValueError):pass
    return x,m
def fill_and_normalize(x,mask):
    x=np.asarray(x,dtype=np.float32); mask=np.asarray(mask,dtype=np.float32)
    med=np.nanmedian(np.where(mask>0,x,np.nan),axis=0)
    med=np.where(np.isfinite(med),med,0).astype(np.float32)
    x=np.where(np.isfinite(x),x,med)
    return x,mask
