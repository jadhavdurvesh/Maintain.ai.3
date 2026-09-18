"""Shared category-aware temporal model."""
import torch
from torch import nn
class SharedTemporalModel(nn.Module):
    def __init__(self,sensor_count=7,category_count=5,hidden=128,horizons=3):
        super().__init__()
        self.category=nn.Embedding(category_count,16)
        self.encoder=nn.Sequential(nn.Conv1d(sensor_count,64,5,padding=2),nn.GELU(),nn.Conv1d(64,hidden,5,padding=2),nn.GELU())
        self.temporal=nn.GRU(hidden,hidden,batch_first=True)
        self.norm=nn.LayerNorm(hidden+16)
        self.risk=nn.Sequential(nn.Linear(hidden+16,64),nn.GELU(),nn.Linear(64,horizons))
        self.rul=nn.Sequential(nn.Linear(hidden+16,64),nn.GELU(),nn.Linear(64,1))
    def forward(self,x,category_id):
        z=self.encoder(x.transpose(1,2)).transpose(1,2)
        z,_=self.temporal(z); z=z[:,-1,:]
        z=self.norm(torch.cat([z,self.category(category_id)],dim=-1))
        return {"risk_logits":self.risk(z),"rul_hours":self.rul(z).squeeze(-1)}
