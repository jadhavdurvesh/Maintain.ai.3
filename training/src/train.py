"""Train the shared temporal model from real prepared sequence tensors."""
import argparse, random
from pathlib import Path
import numpy as np, torch
from torch import nn
from torch.utils.data import DataLoader,TensorDataset
from model import SharedTemporalModel

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--data",required=True)
    p.add_argument("--epochs",type=int,default=50)
    p.add_argument("--batch-size",type=int,default=128)
    p.add_argument("--lr",type=float,default=3e-4)
    p.add_argument("--out",default="artifacts/shared_temporal.pt")
    p.add_argument("--seed",type=int,default=42)
    a=p.parse_args()
    random.seed(a.seed); np.random.seed(a.seed); torch.manual_seed(a.seed)
    path=Path(a.data)
    if not path.exists(): raise SystemExit(f"Prepared real dataset not found: {path}")
    payload=torch.load(path,map_location="cpu",weights_only=False)
    required=("x","category_id","risk_target","rul_target","rul_mask")
    missing=[k for k in required if k not in payload]
    if missing: raise SystemExit(f"Prepared tensor file missing: {missing}")
    ds=TensorDataset(payload["x"],payload["category_id"],payload["risk_target"],payload["rul_target"],payload["rul_mask"],payload.get("risk_mask",torch.zeros_like(payload["risk_target"])))
    dl=DataLoader(ds,batch_size=a.batch_size,shuffle=True)
    device=torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model=SharedTemporalModel().to(device)
    opt=torch.optim.AdamW(model.parameters(),lr=a.lr,weight_decay=1e-4)
    bce=nn.BCEWithLogitsLoss(); mse=nn.SmoothL1Loss()
    for epoch in range(a.epochs):
        model.train(); total=0.0
        for x,c,y,r,m,rm in dl:
            x,c,y,r,m,rm=[v.to(device) for v in (x,c,y,r,m,rm)]
            opt.zero_grad(); out=model(x,c); loss=torch.zeros((),device=device)
            if rm.any(): loss=loss+bce(out["risk_logits"][rm],y[rm])
            if m.any(): loss=loss+0.25*mse(out["rul_hours"][m],r[m])
            if loss.requires_grad: loss.backward(); opt.step()
            total+=float(loss.detach())
        print(f"epoch={epoch+1}/{a.epochs} loss={total/max(1,len(dl)):.5f} device={device}")
    out=Path(a.out); out.parent.mkdir(parents=True,exist_ok=True)
    torch.save({"model":model.cpu().state_dict(),"version":"shared-temporal-v1","sensor_count":28,"category_count":5},out)
    print(f"saved={out}")
if __name__=="__main__": main()
