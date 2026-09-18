"""Train from prepared real sequence tensors; never fabricate telemetry."""
import argparse
from pathlib import Path
import torch
from torch import nn
from torch.utils.data import DataLoader,TensorDataset
from model import SharedTemporalModel
def main():
    p=argparse.ArgumentParser(); p.add_argument("--data",required=True); p.add_argument("--epochs",type=int,default=50); p.add_argument("--batch-size",type=int,default=128); p.add_argument("--out",default="artifacts/shared_temporal.pt"); a=p.parse_args()
    path=Path(a.data)
    if not path.exists(): raise SystemExit(f"Prepared real dataset not found: {path}")
    payload=torch.load(path,map_location="cpu")
    model=SharedTemporalModel()
    ds=TensorDataset(payload["x"],payload["category_id"],payload["risk_target"],payload["rul_target"],payload["rul_mask"])
    dl=DataLoader(ds,batch_size=a.batch_size,shuffle=True)
    opt=torch.optim.AdamW(model.parameters(),lr=3e-4,weight_decay=1e-4); bce=nn.BCEWithLogitsLoss(); mse=nn.SmoothL1Loss()
    model.train()
    for epoch in range(a.epochs):
        total=0.0
        for x,c,y,r,m in dl:
            opt.zero_grad(); out=model(x,c); loss=bce(out["risk_logits"],y)
            if m.any(): loss=loss+0.25*mse(out["rul_hours"][m],r[m])
            loss.backward(); opt.step(); total+=float(loss.detach())
        print(f"epoch={epoch+1} loss={total/max(1,len(dl)):.5f}")
    out=Path(a.out); out.parent.mkdir(parents=True,exist_ok=True); torch.save({"model":model.state_dict(),"version":"shared-temporal-v1"},out)
if __name__=="__main__": main()
