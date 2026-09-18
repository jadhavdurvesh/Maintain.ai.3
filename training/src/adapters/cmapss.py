"""NASA C-MAPSS text adapter.
Expected files such as train_FD001.txt / test_FD001.txt. C-MAPSS rows contain
unit id, cycle, 3 operating settings and 21 sensor channels.
"""
from pathlib import Path
import pandas as pd
COLS=["unit_id","cycle","op_1","op_2","op_3"]+[f"sensor_{i}" for i in range(1,22)]
def load(path):
    df=pd.read_csv(path,sep=r"\s+",header=None,names=COLS,engine="python")
    df["asset_id"]=df["unit_id"].map(lambda x:f"cmapss_{int(x)}")
    df["timestamp"]=df["cycle"].astype(float)
    df["category"]="other"
    df["source"]="nasa_cmapss"
    df["rul_hours"]=df.groupby("unit_id")["cycle"].transform("max")-df["cycle"]
    return df
