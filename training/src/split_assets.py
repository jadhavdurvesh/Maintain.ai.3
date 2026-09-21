"""Deterministic asset-level split helper.

Use this before sequence generation. It prevents adjacent windows from the
same physical asset/run leaking into train and test.
"""
import argparse, hashlib, pandas as pd
def bucket(asset,seed):
    h=int(hashlib.sha256(f"{seed}:{asset}".encode()).hexdigest()[:8],16)%100
    return "test" if h<15 else ("val" if h<30 else "train")
def main():
    p=argparse.ArgumentParser();p.add_argument("--input",required=True);p.add_argument("--out-dir",required=True);p.add_argument("--seed",type=int,default=42);a=p.parse_args()
    df=pd.read_parquet(a.input); df["split"]=df["asset_id"].map(lambda x:bucket(x,a.seed))
    for name,g in df.groupby("split"):
        path=f"{a.out_dir}/{name}.parquet";g.drop(columns=["split"]).to_parquet(path,index=False);print(name,len(g),g.asset_id.nunique(),path)
if __name__=="__main__":main()
