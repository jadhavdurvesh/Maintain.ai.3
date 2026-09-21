"""Create leakage-safe temporal sequences from normalized dataset rows.

This builder is intended for bootstrap degradation pretraining. Public
datasets do not share a physical hour, so RUL is stored as source-native
remaining steps. MAINTAIN AI's 24h/48h/7d labels are built later from real
timestamps and confirmed failures.
"""
import argparse
from pathlib import Path
import numpy as np, pandas as pd, torch
from adapters.common import to_vector,fill_and_normalize
CATEGORY={"induction_motor":0,"pump":1,"compressor":2,"conveyor":3,"other":4}
def main():
    p=argparse.ArgumentParser();p.add_argument("--input",required=True);p.add_argument("--out",required=True);p.add_argument("--sequence-length",type=int,default=24);a=p.parse_args()
    df=pd.read_parquet(a.input)
    required={"asset_id","timestamp","category"}
    missing=required-set(df.columns)
    if missing: raise SystemExit(f"Missing columns: {sorted(missing)}")
    xs=[];cs=[];rs=[];rm=[]
    for asset,g in df.groupby("asset_id",sort=False):
        g=g.sort_values("timestamp").reset_index(drop=True)
        if len(g)<a.sequence_length: continue
        vectors=[];masks=[]
        for _,row in g.iterrows():
            x,m=to_vector(row.to_dict());vectors.append(x);masks.append(m)
        vectors=np.stack(vectors);masks=np.stack(masks); vectors,_=fill_and_normalize(vectors,masks)
        # Standardize each channel within the asset to expose temporal shape.
        mu=np.nanmean(vectors,axis=0);sd=np.nanstd(vectors,axis=0);sd=np.where(sd<1e-6,1,sd);vectors=(vectors-mu)/sd
        for end in range(a.sequence_length-1,len(g)):
            start=end-a.sequence_length+1
            target=g.iloc[end].get("rul_hours",np.nan)
            if pd.isna(target): target=g.iloc[end].get("rul_steps",np.nan)
            if pd.isna(target): continue
            xs.append(vectors[start:end+1]);cs.append(CATEGORY.get(str(g.iloc[end]["category"]),4));rs.append(float(target));rm.append(1.0)
    if not xs: raise SystemExit("No usable real sequences found.")
    out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
    torch.save({"x":torch.tensor(np.stack(xs),dtype=torch.float32),"category_id":torch.tensor(cs,dtype=torch.long),"risk_target":torch.zeros((len(xs),3),dtype=torch.float32),"rul_target":torch.tensor(rs,dtype=torch.float32),"rul_mask":torch.tensor(rm,dtype=torch.bool),"risk_mask":torch.zeros((len(xs),3),dtype=torch.bool)},out)
    print(f"sequences={len(xs)} assets={df.asset_id.nunique()} output={out}")
if __name__=="__main__":main()
