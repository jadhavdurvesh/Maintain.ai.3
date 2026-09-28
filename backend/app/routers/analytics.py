from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime

from ..database import get_db, SessionLocal
from ..ml import model as risk_model
from ..ml.online import score_machine
from ..ml.temporal import artifact_status as temporal_artifact_status
from ..ml.pretrained import pretrained_status, score_machine as score_pretrained_machine
from ..ml.forecasts import forecast_status as forecast_models_status, forecast_signal as chronos_forecast
from ..ml.timer import timer_status, forecast as timer_forecast
from ..ml.degradation import get_timeline
from ..ml.intelligence import process_telemetry
from ..ml.risk_horizons import risk_readiness, fleet_intelligence
from ..ml import advanced as advanced_model
from .. import models
from ..deps import get_current_user, CurrentUser

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

def _visible_machine_ids(db: Session, current: CurrentUser):
    q = db.query(models.Machine.id).filter(models.Machine.organization_id == current.organization_id, models.Machine.archived.is_(False))
    if current.id is not None and current.role == models.UserRole.technician.value:
        q = q.join(models.UserMachineAssignment, models.UserMachineAssignment.machine_id == models.Machine.id).filter(models.UserMachineAssignment.user_id == current.id)
    return [row[0] for row in q.all()]

def _scoped_machine(db: Session, machine_id: int, current: CurrentUser):
    machine = db.query(models.Machine).filter(models.Machine.id == machine_id, models.Machine.organization_id == current.organization_id, models.Machine.archived.is_(False)).first()
    if not machine:
        raise HTTPException(404, "machine not found")
    if current.id is not None and current.role == models.UserRole.technician.value:
        if not db.query(models.UserMachineAssignment).filter_by(user_id=current.id, machine_id=machine_id).first():
            raise HTTPException(404, "machine not assigned to this worker")
    return machine


@router.get("/model-status")
def get_model_status(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    return risk_model.model_status(db, current.organization_id)

@router.post("/train")
def train_model(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    if current.role != models.UserRole.admin.value:
        raise HTTPException(403, "administrator access required")
    return risk_model.train(db, _visible_machine_ids(db, current), current.organization_id)

@router.get("/risk-predictions")
def get_risk_predictions(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    return risk_model.predict_risk(db, _visible_machine_ids(db, current), current.organization_id)

@router.get("/temporal-model-status")
def get_temporal_model_status():
    return temporal_artifact_status()

@router.get("/pretrained-model-status")
def get_pretrained_model_status():
    return pretrained_status()

@router.get("/machines/{machine_id}/pretrained-anomaly")
def get_pretrained_anomaly(machine_id: int, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    _scoped_machine(db, machine_id, current)
    return score_pretrained_machine(db, machine_id)

@router.get("/machines/{machine_id}/intelligence")
def get_machine_intelligence(machine_id: int, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    _scoped_machine(db, machine_id, current)
    behaviour = score_machine(db, machine_id)
    pretrained = score_pretrained_machine(db, machine_id)
    return {"machine_id": machine_id, "online_behaviour": behaviour, "pretrained_anomaly": pretrained, "failure_probability": None, "failure_probability_status": "not_calibrated"}

@router.get("/machines/{machine_id}/behaviour")
def get_machine_behaviour(machine_id: int, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    _scoped_machine(db, machine_id, current)
    return score_machine(db, machine_id)

@router.get("/live-behaviour")
def get_live_behaviour(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    machines = db.query(models.Machine).filter(models.Machine.id.in_(_visible_machine_ids(db, current))).order_by(models.Machine.id.asc()).all()
    results = []
    for machine in machines:
        behaviour = score_machine(db, machine.id)
        results.append({"machine_id": machine.id, "machine_name": machine.name, "health_score": machine.health_score, "status": machine.status.value if hasattr(machine.status, "value") else machine.status, "behaviour": behaviour})
    return {"machines": results}

@router.get("/machines/{machine_id}/degradation")
def get_machine_degradation(machine_id: int, limit: int = 48, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    _scoped_machine(db, machine_id, current)
    return get_timeline(db, machine_id, limit)

@router.get("/fleet-intelligence")
def get_fleet_intelligence(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    return fleet_intelligence(db, _visible_machine_ids(db, current))

@router.get("/risk-readiness")
def get_risk_readiness(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    return risk_readiness(db, _visible_machine_ids(db, current))

@router.get("/forecast-model-status")
def get_forecast_model_status():
    return {"chronos_2": forecast_models_status(), "timer": timer_status()}

@router.get("/machines/{machine_id}/forecast")
def get_machine_forecast(machine_id: int, reading_type: str = "temperature", model: str = "chronos2", horizon: int = 12, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    machine = _scoped_machine(db, machine_id, current)
    if horizon < 1 or horizon > 96:
        raise HTTPException(400, "horizon must be between 1 and 96")
    rows = db.query(models.SensorReading).filter_by(machine_id=machine_id, reading_type=reading_type).order_by(models.SensorReading.recorded_at.desc(), models.SensorReading.id.desc()).limit(2880).all()
    values = [float(r.value) for r in reversed(rows)]
    if model.lower() in {"timer", "timer-84m"}:
        return {"machine_id": machine_id, "reading_type": reading_type, **timer_forecast(values, horizon)}
    return {"machine_id": machine_id, "reading_type": reading_type, **chronos_forecast(values, horizon)}

@router.get("/advanced-model-status")
def get_advanced_model_status(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    return advanced_model.model_status(db, current.organization_id)

@router.get("/machines/{machine_id}/advanced-risk")
def get_advanced_risk(machine_id: int, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    machine = _scoped_machine(db, machine_id, current)
    return advanced_model.predict_machine(db, machine)

@router.get('/model-lab')
def get_model_lab(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    ids = _visible_machine_ids(db, current)
    machines = db.query(models.Machine).filter(models.Machine.id.in_(ids)).all()
    reading_count = db.query(models.SensorReading).filter(models.SensorReading.machine_id.in_(ids)).count()
    machines_with_readings = sum(1 for m in machines if db.query(models.SensorReading.id).filter_by(machine_id=m.id).first())
    return {'generated_at': datetime.utcnow().isoformat(), 'advanced_model': advanced_model.model_status(db, current.organization_id), 'pretrained': pretrained_status(), 'forecasts': {'chronos_2': forecast_models_status(), 'timer': timer_status()}, 'fleet': fleet_intelligence(db, ids), 'risk_readiness': risk_readiness(db, ids), 'telemetry': {'reading_count': reading_count, 'machines_with_readings': machines_with_readings}}

@router.get('/evidence-feed')
def get_evidence_feed(limit: int = 80, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    limit = max(10, min(int(limit), 200))
    events = []
    visible_ids = _visible_machine_ids(db, current)
    machines = {m.id: m.name for m in db.query(models.Machine).filter(models.Machine.id.in_(visible_ids)).all()}
    def add(kind, ident, machine_id, timestamp, message):
        if timestamp is not None:
            events.append({'id': ident, 'type': kind, 'machine_id': machine_id, 'machine_name': machines.get(machine_id, 'Machine'), 'timestamp': timestamp.isoformat(), 'message': message})
    for r in db.query(models.SensorReading).filter(models.SensorReading.machine_id.in_(visible_ids)).order_by(models.SensorReading.recorded_at.desc(), models.SensorReading.id.desc()).limit(limit).all(): add('telemetry', 'reading-' + str(r.id), r.machine_id, r.recorded_at, str(r.reading_type) + ': ' + str(r.value) + ' ' + str(r.unit or ''))
    for e in db.query(models.MLAnomalyEvent).filter(models.MLAnomalyEvent.machine_id.in_(visible_ids)).order_by(models.MLAnomalyEvent.created_at.desc()).limit(limit).all(): add('anomaly', 'anomaly-' + str(e.id), e.machine_id, e.created_at, e.message)
    for d in db.query(models.MLDegradationSnapshot).filter(models.MLDegradationSnapshot.machine_id.in_(visible_ids)).order_by(models.MLDegradationSnapshot.recorded_at.desc()).limit(limit).all(): add('degradation', 'degradation-' + str(d.id), d.machine_id, d.recorded_at, 'score ' + format(d.degradation_score, '.3f') + ', trend ' + format(d.trend_score, '.3f') + ', active signals ' + str(d.active_signal_count))
    for f in db.query(models.FaultRecord).filter(models.FaultRecord.machine_id.in_(visible_ids)).order_by(models.FaultRecord.reported_date.desc()).limit(limit).all(): add('fault', 'fault-' + str(f.id), f.machine_id, f.reported_date, f.description + ((' · cause: ' + f.cause) if f.cause else ''))
    for w in db.query(models.WorkOrder).filter(models.WorkOrder.machine_id.in_(visible_ids)).order_by(models.WorkOrder.created_at.desc()).limit(limit).all(): add('work_order', 'workorder-' + str(w.id), w.machine_id, w.created_at, str(w.status.value if hasattr(w.status, 'value') else w.status) + ': ' + w.problem)
    for o in db.query(models.MLOutcomeFeedback).filter(models.MLOutcomeFeedback.machine_id.in_(visible_ids)).order_by(models.MLOutcomeFeedback.created_at.desc()).limit(limit).all(): add('outcome', 'outcome-' + str(o.id), o.machine_id, o.created_at, o.outcome_type + ((' · ' + o.confirmed_root_cause) if o.confirmed_root_cause else ''))
    for s in db.query(models.MachineSafetyEvent).filter(models.MachineSafetyEvent.machine_id.in_(visible_ids)).order_by(models.MachineSafetyEvent.created_at.desc()).limit(limit).all(): add('safety', 'safety-' + str(s.id), s.machine_id, s.created_at, s.message)
    events.sort(key=lambda item: item['timestamp'], reverse=True)
    return {'events': events[:limit], 'count': min(len(events), limit), 'sources': ['sensor_readings', 'ml_anomaly_events', 'ml_degradation_snapshots', 'fault_records', 'work_orders', 'ml_outcome_feedback', 'machine_safety_events']}

# Stable prediction aliases. These live in the already-loaded analytics router so
# the Model Lab keeps working even if a provider has not yet rolled out the newer
# dedicated prediction module. The aliases use the same database records/models.
def _prediction_helpers():
    from ..ml.forecast_runs import MLForecastRun
    from ..ml.forecasting import serialize_run, _interval_seconds, _telemetry_is_fresh
    return MLForecastRun, serialize_run, _interval_seconds, _telemetry_is_fresh

@router.get('/machines/{machine_id}/prediction-status')
def prediction_status_alias(machine_id: int, reading_type: str = 'temperature', model: str = 'chronos-bolt-tiny', horizon: int = 12, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    _scoped_machine(db, machine_id, current)
    MLForecastRun, serialize_run, interval_seconds, telemetry_is_fresh = _prediction_helpers()
    latest = db.query(models.SensorReading).filter_by(machine_id=machine_id, reading_type=reading_type).order_by(models.SensorReading.recorded_at.desc(), models.SensorReading.id.desc()).first()
    run = db.query(MLForecastRun).filter_by(machine_id=machine_id, reading_type=reading_type, model=model, horizon=horizon).filter(MLForecastRun.status == 'completed').order_by(MLForecastRun.created_at.desc()).first()
    return {'machine_id':machine_id,'reading_type':reading_type,'model':model,'horizon':horizon,'telemetry_active':telemetry_is_fresh(latest.recorded_at) if latest else False,'latest_telemetry_at':latest.recorded_at.isoformat() if latest else None,'latest_telemetry_id':latest.id if latest else None,'latest_value':float(latest.value) if latest else None,'sample_count':db.query(models.SensorReading.id).filter_by(machine_id=machine_id, reading_type=reading_type).count(),'interval_seconds':interval_seconds(),'minimum_samples':32,'latest_run':serialize_run(run) if run else None}

@router.get('/machines/{machine_id}/prediction-history')
def prediction_history_alias(machine_id: int, reading_type: str = 'temperature', model: str = 'chronos-bolt-tiny', horizon: int | None = None, forecast_window: str | None = None, limit: int = 50, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    _scoped_machine(db, machine_id, current)
    MLForecastRun, serialize_run, _, _ = _prediction_helpers()
    limit = max(1, min(int(limit), 200))
    q = db.query(MLForecastRun).filter(MLForecastRun.machine_id == machine_id, MLForecastRun.reading_type == reading_type, MLForecastRun.model == model)
    if horizon is not None: q = q.filter(MLForecastRun.horizon == horizon)
    if forecast_window: q = q.filter(MLForecastRun.forecast_window == forecast_window)
    runs = q.order_by(MLForecastRun.created_at.desc()).limit(limit).all()
    return {'machine_id':machine_id,'reading_type':reading_type,'model':model,'horizon':horizon,'forecast_window':forecast_window,'runs':[serialize_run(run) for run in runs],'count':len(runs),'generated_at':datetime.utcnow().isoformat()}

@router.get('/machines/{machine_id}/prediction-windows')
def prediction_windows_alias(machine_id: int, reading_type: str = 'temperature', model: str = 'chronos-bolt-tiny', current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    _scoped_machine(db, machine_id, current)
    from ..ml.forecast_windows import WINDOWS
    MLForecastRun, serialize_run, _, _ = _prediction_helpers()
    result={}
    for window, spec in WINDOWS.items():
        run=db.query(MLForecastRun).filter(MLForecastRun.machine_id==machine_id,MLForecastRun.reading_type==reading_type,MLForecastRun.model==model,MLForecastRun.forecast_window==window,MLForecastRun.status=='completed').order_by(MLForecastRun.created_at.desc()).first()
        result[window]=serialize_run(run) if run else {'available':False,'window':window,'reason':'No forecast generated yet.'}
        result[window]['step_seconds']=spec['step_seconds']; result[window]['steps']=spec['steps']
    return {'machine_id':machine_id,'reading_type':reading_type,'model':model,'windows':result}

@router.get('/machines/{machine_id}/prediction-windows/run')
def prediction_window_run_alias(machine_id: int, window: str = '24h', reading_type: str = 'temperature', model: str = 'chronos-bolt-tiny', current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    machine=_scoped_machine(db,machine_id,current)
    from ..ml.forecast_windows import WINDOWS, _run_window
    if window not in WINDOWS: raise HTTPException(400,'window must be one of 24h, 48h, 7d, 30d')
    try: return _run_window(db,machine,reading_type,window,model,'manual',force=True)
    except Exception as exc:
        db.rollback(); raise HTTPException(502,str(exc)) from exc

# Keep the legacy /api/predictions/* paths functional through this already-loaded router.
@router.get('/machines/{machine_id}/status')
def prediction_status_legacy(machine_id: int, reading_type: str = 'temperature', model: str = 'chronos-bolt-tiny', horizon: int = 12, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    return prediction_status_alias(machine_id,reading_type,model,horizon,current,db)

@router.get('/machines/{machine_id}/history')
def prediction_history_legacy(machine_id: int, reading_type: str = 'temperature', model: str = 'chronos-bolt-tiny', horizon: int | None = None, forecast_window: str | None = None, limit: int = 50, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    return prediction_history_alias(machine_id,reading_type,model,horizon,forecast_window,limit,current,db)

@router.get('/machines/{machine_id}/windows')
def prediction_windows_legacy(machine_id: int, reading_type: str = 'temperature', model: str = 'chronos-bolt-tiny', current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    return prediction_windows_alias(machine_id,reading_type,model,current,db)

@router.get('/machines/{machine_id}/windows/run')
def prediction_window_run_legacy(machine_id: int, window: str = '24h', reading_type: str = 'temperature', model: str = 'chronos-bolt-tiny', current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    return prediction_window_run_alias(machine_id,window,reading_type,model,current,db)

@router.get('/fleet/windows')
def prediction_fleet_windows_legacy(reading_type: str = 'temperature', model: str = 'chronos-bolt-tiny', current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    from ..ml.forecast_windows import WINDOWS
    MLForecastRun, serialize_run, _, _ = _prediction_helpers()
    machine_ids=_visible_machine_ids(db,current)
    machines={m.id:m for m in db.query(models.Machine).filter(models.Machine.id.in_(machine_ids)).all()}
    rows=[]
    for machine_id,machine in machines.items():
        latest=db.query(models.SensorReading).filter_by(machine_id=machine_id,reading_type=reading_type).order_by(models.SensorReading.recorded_at.desc()).first()
        row={'machine_id':machine_id,'machine_name':machine.name,'category':machine.category,'telemetry_at':latest.recorded_at.isoformat() if latest else None,'windows':{}}
        for window in WINDOWS:
            run=db.query(MLForecastRun).filter(MLForecastRun.machine_id==machine_id,MLForecastRun.reading_type==reading_type,MLForecastRun.model==model,MLForecastRun.forecast_window==window,MLForecastRun.status=='completed').order_by(MLForecastRun.created_at.desc()).first()
            row['windows'][window]=serialize_run(run) if run else {'available':False,'window':window,'reason':'No forecast generated yet.'}
        rows.append(row)
    return {'generated_at':datetime.utcnow().isoformat(),'reading_type':reading_type,'model':model,'windows':list(WINDOWS),'machines':rows}
