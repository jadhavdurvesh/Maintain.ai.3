"""Evaluate RUL predictions on a held-out prepared tensor file."""
import argparse, json
from pathlib import Path
import numpy as np, torch
from model import SharedTemporalModel
def main():
    p=argparse.ArgumentParser();p.add_argument("--data",required=True);p.add_argument("--model",required=True);p.add_argument("--out",default="artifacts/evaluation.json");a=p.parse_args()
    d=torch.load(a.data,map_location="cpu",weights_only=False); model=SharedTemporalModel(); ck=torch.load(a.model,map_location="cpu",weights_only=False); model.load_state_dict(ck["model"]); model.eval()
    with torch.no_grad(): pred=model(d["x"],d["category_id"])["rul_hours"].numpy()
    mask=d["rul_mask"].numpy().astype(bool); y=d["rul_target"].numpy()
    if not mask.any(): raise SystemExit("No valid RUL targets in evaluation data.")
    err=pred[mask]-y[mask]
    result={"samples":int(mask.sum()),"mae":float(np.mean(np.abs(err))),"rmse":float(np.sqrt(np.mean(err**2))),"prediction_min":float(pred[mask].min()),"prediction_max":float(pred[mask].max())}
    Path(a.out).parent.mkdir(parents=True,exist_ok=True);Path(a.out).write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))
if __name__=="__main__":main()
