"""Rolling telemetry feature extraction for Phase 1."""
import json
import math
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from .. import models

SENSOR_TYPES = ("temperature", "vibration", "current", "load")
WINDOWS = (300, 900, 3600)

def _stats(values):
    if not values:
        return {"count":0,"mean":0.0,"std":0.0,"min":0.0,"max":0.0,"slope":0.0,"delta":0.0}
    n=len(values); mean=sum(values)/n
    variance=sum((v-mean)**2 for v in values)/max(n-1,1)
    slope=0.0
    if n>=2:
        xm=(n-1)/2
        denom=sum((i-xm)**2 for i in range(n))
        slope=sum((i-xm)*(v-mean) for i,v in enumerate(values))/denom if denom else 0.0
    return {"count":n,"mean":round(mean,6),"std":round(math.sqrt(max(variance,0)),6),"min":round(min(values),6),"max":round(max(values),6),"slope":round(slope,6),"delta":round(values[-1]-values[0],6)}

def build_window_features(db: Session, machine_id: int, window_end: datetime, window_seconds: int):
    start=window_end-timedelta(seconds=window_seconds)
    readings=(db.query(models.SensorReading).filter(models.SensorReading.machine_id==machine_id).filter(models.SensorReading.recorded_at>start,models.SensorReading.recorded_at<=window_end).order_by(models.SensorReading.recorded_at.asc(),models.SensorReading.id.asc()).all())
    by_type={k:[] for k in SENSOR_TYPES}
    for r in readings:
        k=(r.reading_type or "").lower().strip()
        if k in by_type:
            try:
                v=float(r.value)
                if math.isfinite(v): by_type[k].append(v)
            except (TypeError,ValueError): pass
    features={"window_seconds":window_seconds,"sample_count":len(readings)}
    for k in SENSOR_TYPES:
        for name,value in _stats(by_type[k]).items(): features[f"{k}_{name}"]=value
    pairs=(("vibration","load","vibration_load_ratio"),("current","load","current_load_ratio"),("temperature","vibration","temperature_vibration_ratio"))
    for a,b,name in pairs:
        if by_type[a] and by_type[b]:
            features[name]=round((sum(by_type[a])/len(by_type[a]))/max(sum(by_type[b])/len(by_type[b]),1e-9),6)
    return features

def materialize_windows(db: Session, machine_id: int, window_end: datetime|None=None):
    end=window_end or datetime.utcnow()
    rows=[]
    for seconds in WINDOWS:
        features=build_window_features(db,machine_id,end,seconds)
        row=(db.query(models.MLTelemetryWindow).filter_by(machine_id=machine_id,window_end=end,window_seconds=seconds).first())
        if row:
            row.sample_count=features["sample_count"]; row.feature_json=json.dumps(features,separators=(",",":"))
        else:
            row=models.MLTelemetryWindow(machine_id=machine_id,window_end=end,window_seconds=seconds,sample_count=features["sample_count"],feature_json=json.dumps(features,separators=(",",":"))); db.add(row)
        rows.append(row)
    db.flush()
    return rows
