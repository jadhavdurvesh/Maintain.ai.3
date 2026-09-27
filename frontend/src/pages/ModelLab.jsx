import { useEffect, useMemo, useState } from 'react'
import { BrainCircuit, Radio, ShieldCheck, Timer, TrendingUp, ChevronRight, Activity, Target, Gauge } from 'lucide-react'
import api from '../api/client.js'
import { formatDateTime } from '../utils/dates.js'
import { usePageHeader } from '../PageHeaderContext.jsx'

const fmt = (v, digits = 2) => v == null || Number.isNaN(Number(v)) ? '—' : Number(v).toFixed(digits)

function Status({ ok, children }) {
  return <span className={'badge ' + (ok ? 'healthy' : 'warning')}>{children}</span>
}

function MiniSeries({ actual = [], forecast = [] }) {
  const values = [...actual.slice(-32), ...forecast.slice(0, 12)].map(Number).filter(Number.isFinite)
  if (!values.length) return <div className="empty-state">No signal values available yet.</div>
  const min = Math.min(...values)
  const max = Math.max(...values)
  const range = max - min || 1
  const width = 760
  const height = 190
  const toPoint = (value, index, count) => `${(index / Math.max(count - 1, 1)) * width},${height - ((value - min) / range) * (height - 20) - 10}`
  const actualPoints = actual.slice(-32).map(Number).filter(Number.isFinite).map((v, i, arr) => toPoint(v, i, arr.length)).join(' ')
  const allCount = actual.slice(-32).length + forecast.slice(0, 12).length
  const forecastPoints = forecast.slice(0, 12).map(Number).filter(Number.isFinite).map((v, i) => toPoint(v, actual.slice(-32).length + i, allCount)).join(' ')
  const splitX = (actual.slice(-32).length - 1) / Math.max(allCount - 1, 1) * width
  return (
    <div style={{ overflowX: 'auto', background: 'var(--panel-raised)', border: '1px solid var(--border)', borderRadius: 10, padding: 10 }}>
      <svg viewBox={`0 0 ${width} ${height}`} width="100%" height="190" role="img" aria-label="Historical and forecast signal chart">
        <line x1="0" y1="50" x2={width} y2="50" stroke="var(--border)" />
        <line x1="0" y1="95" x2={width} y2="95" stroke="var(--border)" />
        <line x1="0" y1="140" x2={width} y2="140" stroke="var(--border)" />
        <line x1={splitX} y1="0" x2={splitX} y2={height} stroke="var(--text-faint)" strokeDasharray="5 5" />
        {actualPoints && <polyline fill="none" stroke="var(--accent)" strokeWidth="3" points={actualPoints} />}
        {forecastPoints && <polyline fill="none" stroke="var(--warning)" strokeWidth="3" strokeDasharray="7 5" points={forecastPoints} />}
        <text x="8" y="18" fill="var(--text-faint)" fontSize="11">actual</text>
        <text x={Math.min(splitX + 8, width - 90)} y="18" fill="var(--warning)" fontSize="11">forecast</text>
      </svg>
      <div style={{display:'flex',justifyContent:'space-between',fontSize:10,color:'var(--text-faint)'}}>
        <span>Older telemetry</span><span>Now → predicted future</span>
      </div>
    </div>
  )
}

function PredictionSummary({ forecast, actual }) {
  const predicted = (forecast?.forecast || []).map(Number).filter(Number.isFinite)
  const history = (actual || []).map(Number).filter(Number.isFinite)
  if (!predicted.length) return null
  const first = predicted[0]
  const last = predicted[predicted.length - 1]
  const baseline = history.length ? history[history.length - 1] : null
  const delta = baseline == null ? null : first - baseline
  const totalDelta = baseline == null ? null : last - baseline
  const direction = totalDelta == null || Math.abs(totalDelta) < 0.000001 ? 'Stable' : totalDelta > 0 ? 'Increasing' : 'Decreasing'
  return (
    <div className="stat-grid" style={{marginTop:12}}>
      <div className="stat-tile"><div className="stat-label"><Target size={14} style={{verticalAlign:'-3px',marginRight:5}}/>NEXT PREDICTION</div><div className="stat-value" style={{fontSize:22}}>{fmt(first)}</div><div style={{color:'var(--text-faint)',fontSize:11}}>t+1</div></div>
      <div className="stat-tile"><div className="stat-label"><TrendingUp size={14} style={{verticalAlign:'-3px',marginRight:5}}/>END OF HORIZON</div><div className="stat-value" style={{fontSize:22}}>{fmt(last)}</div><div style={{color:'var(--text-faint)',fontSize:11}}>t+{predicted.length}</div></div>
      <div className="stat-tile"><div className="stat-label"><Gauge size={14} style={{verticalAlign:'-3px',marginRight:5}}/>EXPECTED TREND</div><div className="stat-value" style={{fontSize:22}}>{direction}</div><div style={{color:'var(--text-faint)',fontSize:11}}>{totalDelta == null ? 'No baseline' : `${totalDelta >= 0 ? '+' : ''}${fmt(totalDelta)} vs latest`}</div></div>
      <div className="stat-tile"><div className="stat-label"><Activity size={14} style={{verticalAlign:'-3px',marginRight:5}}/>MODEL OUTPUT</div><div className="stat-value" style={{fontSize:22}}>{fmt(delta)}</div><div style={{color:'var(--text-faint)',fontSize:11}}>first step vs latest</div></div>
    </div>
  )
}

export default function ModelLab() {
  usePageHeader('AI Monitoring / Model Lab')
  const [data, setData] = useState(null)
  const [evidence, setEvidence] = useState(null)
  const [error, setError] = useState(null)
  const [selectedMachine, setSelectedMachine] = useState(null)
  const [machineEvidence, setMachineEvidence] = useState(null)
  const [machineBusy, setMachineBusy] = useState(false)
  const [predictionMachineId, setPredictionMachineId] = useState('')
  const [predictionType, setPredictionType] = useState('temperature')
  const [predictionModel, setPredictionModel] = useState('chronos2')
  const [predictionHorizon, setPredictionHorizon] = useState(12)
  const [prediction, setPrediction] = useState(null)
  const [predictionActual, setPredictionActual] = useState([])
  const [predictionBusy, setPredictionBusy] = useState(false)
  const [predictionError, setPredictionError] = useState(null)

  const load = async () => {
    try {
      const [lab, ev] = await Promise.all([
        api.get('/api/analytics/model-lab'),
        api.get('/api/analytics/evidence-feed?limit=80'),
      ])
      setData(lab); setEvidence(ev); setError(null)
      if (!predictionMachineId && lab?.fleet?.machines?.length) setPredictionMachineId(String(lab.fleet.machines[0].machine_id))
    } catch (e) { setError(e.message) }
  }

  useEffect(() => {
    load()
    const timer = window.setInterval(load, 15000)
    return () => window.clearInterval(timer)
  }, [])

  const runPrediction = async () => {
    if (!predictionMachineId) return
    setPredictionBusy(true)
    setPredictionError(null)
    try {
      const [result, readings] = await Promise.all([
        api.get(`/api/analytics/machines/${predictionMachineId}/forecast?reading_type=${encodeURIComponent(predictionType)}&model=${predictionModel}&horizon=${predictionHorizon}`),
        api.get(`/api/machines/${predictionMachineId}/readings?limit=64`),
      ])
      setPrediction(result)
      setPredictionActual((readings || []).filter(r => r.reading_type === predictionType).map(r => Number(r.value)).filter(Number.isFinite).slice(-32))
    } catch (e) {
      setPrediction(null)
      setPredictionActual([])
      setPredictionError(e?.message || 'Prediction request failed.')
    } finally {
      setPredictionBusy(false)
    }
  }

  const openMachine = async (machine) => {
    setSelectedMachine(machine)
    setMachineBusy(true)
    try {
      const [ev, intel, degradation] = await Promise.all([
        api.get('/api/analytics/evidence-feed?machine_id=' + machine.machine_id + '&limit=120'),
        api.get('/api/analytics/machines/' + machine.machine_id + '/intelligence'),
        api.get('/api/analytics/machines/' + machine.machine_id + '/degradation?limit=48'),
      ])
      setMachineEvidence({ ...ev, intelligence: intel, degradation: degradation.points || [] })
    } catch (e) { setMachineEvidence({ error: e.message }) }
    finally { setMachineBusy(false) }
  }

  const selectedMachineName = useMemo(() => data?.fleet?.machines?.find(m => String(m.machine_id) === String(predictionMachineId))?.machine_name || 'Machine', [data, predictionMachineId])
  const cards = useMemo(() => {
    if (!data) return []
    return [
      { icon: BrainCircuit, title: 'TimeRadar', value: data.pretrained?.available ? 'Ready' : 'Optional', detail: data.pretrained?.model || 'Zero-shot anomaly model' },
      { icon: TrendingUp, title: 'Chronos-2', value: data.forecasts?.chronos_2?.available ? 'Ready' : 'Optional', detail: 'Zero-shot signal forecasting' },
      { icon: Timer, title: 'Timer', value: data.forecasts?.timer?.available ? 'Ready' : 'Optional', detail: 'Zero-shot signal forecasting' },
      { icon: BrainCircuit, title: 'Advanced model', value: data.advanced_model?.trained ? 'Trained' : 'Not trained', detail: data.advanced_model?.model_type || 'Supervised temporal model' },
      { icon: Radio, title: 'Live telemetry', value: data.telemetry?.machines_with_readings ?? 0, detail: (data.telemetry?.reading_count ?? 0) + ' recent readings' },
    ]
  }, [data])

  if (error && !data) return <div className="panel"><div className="panel-body">Model Lab error: {error}</div></div>
  if (!data) return <div className="panel"><div className="panel-body">Loading model telemetry…</div></div>

  return (
    <>
      <div className="panel section-gap">
        <div className="panel-header"><span className="panel-title">Temporal Intelligence Monitor</span><span className="badge neutral">Live · refresh 15s</span></div>
        <div className="panel-body"><p style={{color:'var(--text-dim)',fontSize:13,margin:0}}>This page now connects model output to an actual machine signal: historical telemetry → pretrained model → future signal values → interpretable trend. It does not invent failure probabilities.</p></div>
      </div>

      <div className="stat-grid">
        {cards.map(({icon:Icon,title,value,detail}) => <div className="stat-tile" key={title}><div className="stat-label"><Icon size={14} style={{verticalAlign:'-3px',marginRight:5}} />{title}</div><div className="stat-value" style={{fontSize:22}}>{value}</div><div style={{color:'var(--text-faint)',fontSize:11,marginTop:5}}>{detail}</div></div>)}
      </div>

      <div className="panel section-gap" style={{border:'1px solid var(--accent)',boxShadow:'0 0 28px rgba(0,200,255,.07)'}}>
        <div className="panel-header">
          <span className="panel-title">Prediction Center</span>
          <span className="badge neutral">Model output · not a failure probability</span>
        </div>
        <div className="panel-body">
          <div className="grid-2" style={{marginBottom:12}}>
            <label>Machine
              <select value={predictionMachineId} onChange={e=>{setPredictionMachineId(e.target.value);setPrediction(null);setPredictionError(null)}}>
                {data.fleet?.machines?.map(m => <option key={m.machine_id} value={m.machine_id}>{m.machine_name} · {m.category || 'other'}</option>)}
              </select>
            </label>
            <label>Signal
              <select value={predictionType} onChange={e=>{setPredictionType(e.target.value);setPrediction(null);setPredictionError(null)}}>
                <option value="temperature">Temperature</option>
                <option value="vibration">Vibration</option>
                <option value="current">Motor Current</option>
                <option value="load">Machine Load</option>
                <option value="humidity">Humidity</option>
              </select>
            </label>
            <label>Forecast model
              <select value={predictionModel} onChange={e=>{setPredictionModel(e.target.value);setPrediction(null);setPredictionError(null)}}>
                <option value="chronos2">Chronos-2</option>
                <option value="timer">Timer</option>
              </select>
            </label>
            <label>Prediction horizon
              <select value={predictionHorizon} onChange={e=>setPredictionHorizon(Number(e.target.value))}>
                <option value="6">6 steps</option><option value="12">12 steps</option><option value="24">24 steps</option>
              </select>
            </label>
          </div>
          <div className="chip-row">
            <button className="btn" onClick={runPrediction} disabled={predictionBusy || !predictionMachineId}>{predictionBusy ? 'Running model…' : 'Run prediction'}</button>
            <span style={{fontSize:11,color:'var(--text-faint)'}}>Using {selectedMachineName} · {predictionType} · {predictionModel}</span>
          </div>

          {predictionError && <div style={{marginTop:12,padding:10,borderRadius:8,background:'rgba(255,70,70,.10)',color:'var(--critical)',fontSize:12}}>{predictionError}</div>}

          {prediction && !prediction.available && <div style={{marginTop:12,padding:12,borderRadius:8,background:'rgba(255,180,0,.08)',color:'var(--warning)',fontSize:12}}>{prediction.reason || 'This model cannot produce a prediction from the available telemetry.'}</div>}

          {prediction?.available && <>
            <PredictionSummary forecast={prediction} actual={predictionActual} />
            <div style={{marginTop:14}}><MiniSeries actual={predictionActual} forecast={prediction.forecast || []} /></div>
            <div style={{marginTop:12,display:'grid',gridTemplateColumns:'repeat(4,minmax(0,1fr))',gap:8}}>
              {(prediction.forecast || []).slice(0, predictionHorizon).map((value, index) => <div key={index} style={{padding:9,borderRadius:7,background:'var(--panel-raised)',border:'1px solid var(--border)'}}><div className="mono" style={{fontWeight:700}}>{fmt(value)}</div><div style={{fontSize:10,color:'var(--text-faint)',marginTop:3}}>t+{index + 1}</div></div>)}
            </div>
            <div style={{marginTop:12,padding:12,borderRadius:8,background:'var(--panel-raised)',fontSize:12,color:'var(--text-dim)'}}>
              <b>How to read this:</b> the solid line is the machine's recent observed signal. The dashed line is what <span className="mono">{prediction.model || predictionModel}</span> estimates next. A rising forecast means the signal is expected to rise relative to the recent history; it does not by itself mean the machine will fail. Use the forecast together with degradation evidence, safety limits, maintenance history, and technician inspection.
            </div>
          </>}

          {!prediction && !predictionBusy && <div style={{marginTop:14,padding:14,borderRadius:8,background:'var(--panel-raised)',color:'var(--text-dim)',fontSize:12}}>
            <b>What this will answer:</b> “Given this machine's recent sensor history, what values does the selected pretrained model expect over the next {predictionHorizon} steps?” The result is a signal forecast, not a made-up percentage chance of failure.
          </div>}
        </div>
      </div>

      <div className="grid-2 section-gap">
        <div className="panel">
          <div className="panel-header"><span className="panel-title">Model Runtime</span></div>
          <div className="panel-body">
            <div className="chip-row" style={{marginBottom:10}}>
              <Status ok={!!data.pretrained?.available}>{data.pretrained?.available ? 'TimeRadar ready' : 'TimeRadar unavailable'}</Status>
              <Status ok={!!data.forecasts?.chronos_2?.available}>{data.forecasts?.chronos_2?.available ? 'Chronos-2 ready' : 'Chronos-2 optional'}</Status>
              <Status ok={!!data.forecasts?.timer?.available}>{data.forecasts?.timer?.available ? 'Timer ready' : 'Timer optional'}</Status>
              <Status ok={!!data.advanced_model?.trained}>{data.advanced_model?.trained ? 'Advanced model trained' : 'Advanced model not trained'}</Status>
            </div>
            <div style={{display:'grid',gap:8,fontSize:12,color:'var(--text-dim)'}}>
              <div><b>Pretrained anomaly:</b> {data.pretrained?.model || 'TimeRadar'} · zero-shot · no MAINTAIN AI training</div>
              <div><b>Forecasts:</b> Chronos-2 / Timer estimate future sensor values from the selected signal history</div>
              <div><b>Future risk:</b> {data.risk_readiness?.status || 'data collection and validation'}</div>
              <div><b>Last refresh:</b> {formatDateTime(data.generated_at)}</div>
            </div>
          </div>
        </div>
        <div className="panel">
          <div className="panel-header"><span className="panel-title">Risk Data Readiness</span><span className="badge neutral">Not a prediction</span></div>
          <div className="panel-body">
            <div style={{display:'grid',gap:8}}>
              {Object.entries(data.risk_readiness?.horizons || {}).map(([h,v]) => <div key={h} style={{display:'grid',gridTemplateColumns:'55px 1fr 1fr',gap:8,alignItems:'center',fontSize:12}}><span className="mono">{h}</span><span>Labels: <b>{v.complete_labels}</b></span><span>Positive: <b>{v.positive_outcomes}</b> · Negative: <b>{v.negative_outcomes}</b></span></div>)}
            </div>
            <div style={{marginTop:12,color:'var(--text-faint)',fontSize:11}}>Calibrated future failure probabilities remain disabled until enough leakage-safe outcomes are collected and a model is validated.</div>
          </div>
        </div>
      </div>

      <div className="panel section-gap">
        <div className="panel-header"><span className="panel-title">Fleet Temporal Signals</span><span className="badge neutral">{data.fleet?.count || 0} machines</span></div>
        <table><thead><tr><th>Machine</th><th>Category</th><th>Health</th><th>Degradation</th><th>Trend</th><th>Signals</th><th>Evidence</th></tr></thead>
          <tbody>{data.fleet?.machines?.map(m => <tr key={m.machine_id} onClick={() => openMachine(m)} style={{cursor:'pointer'}} title="Open machine evidence timeline"><td><button className="btn secondary" style={{padding:'4px 8px'}} onClick={(e)=>{e.stopPropagation();openMachine(m)}}>{m.machine_name} <ChevronRight size={13}/></button></td><td>{m.category || 'other'}</td><td>{m.health_score}/100</td><td className="mono">{fmt(m.degradation_score)}</td><td className="mono">{fmt(m.trend_score)}</td><td className="mono">{m.active_signal_count}</td><td style={{maxWidth:360}}>{(m.evidence || []).map((e,i)=><span key={i} className="badge neutral" style={{margin:'2px 4px 2px 0'}}>{e.reading_type} {fmt(e.anomaly_score)}</span>)}</td></tr>)}</tbody>
        </table>
      </div>

      {selectedMachine && <div className="panel section-gap">
        <div className="panel-header"><span className="panel-title">Machine Evidence · {selectedMachine.machine_name}</span><span className="badge neutral">{machineBusy ? 'Loading…' : 'Selected'}</span></div>
        <div className="panel-body">
          {machineEvidence?.error ? <div style={{color:'var(--critical)',fontSize:12}}>{machineEvidence.error}</div> : machineEvidence ? <div style={{display:'grid',gap:10,fontSize:12,color:'var(--text-dim)'}}>
            <div><b>Intelligence:</b> degradation {fmt(machineEvidence.intelligence?.degradation_score)} · trend {fmt(machineEvidence.intelligence?.trend_score)} · anomaly {fmt(machineEvidence.intelligence?.pretrained_anomaly?.anomaly_score)}</div>
            <div><b>Evidence records:</b> {machineEvidence.events?.length || 0}</div>
            <div><b>Degradation points:</b> {machineEvidence.degradation?.length || 0}</div>
          </div> : <div className="empty-state">Select a machine to inspect its evidence.</div>}
        </div>
      </div>}

      <div className="panel">
        <div className="panel-header"><span className="panel-title">Unified Evidence Feed</span><span className="badge neutral">Point-in-time records</span></div>
        <div className="panel-body">
          {evidence?.events?.length ? <div style={{display:'grid',gap:7}}>{evidence.events.map((e,i) => <div key={e.id + '-' + i} style={{display:'grid',gridTemplateColumns:'150px 110px 1fr',gap:10,padding:'9px 0',borderBottom:'1px solid var(--border)',fontSize:12}}><span className="mono" style={{color:'var(--text-faint)'}}>{formatDateTime(e.timestamp)}</span><span className="badge neutral">{e.type}</span><span><b>{e.machine_name}</b> · {e.message}</span></div>)}</div> : <div className="empty-state">No evidence records yet.</div>}
        </div>
      </div>

      <div className="panel section-gap">
        <div className="panel-header"><span className="panel-title">Interpretation Rules</span><ShieldCheck size={16}/></div>
        <div className="panel-body" style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(220px,1fr))',gap:10}}>
          {[['Anomaly ≠ failure','Anomaly models detect unusual temporal behaviour; they do not prove a future failure.'],['Forecast = future signal','Chronos-2 and Timer forecast the selected sensor value over a chosen horizon.'],['Trend needs context','A rising forecast should be checked against degradation evidence, limits, maintenance history, and inspection.'],['Safety ≠ ML','Safety thresholds remain explicit supervisory controls and must not depend on an unvalidated model.']].map(([title,body]) => <div key={title} style={{padding:12,border:'1px solid var(--border)',borderRadius:10,background:'var(--panel-raised)'}}><b>{title}</b><div style={{color:'var(--text-dim)',fontSize:12,lineHeight:1.5,marginTop:5}}>{body}</div></div>)}
        </div>
      </div>
    </>
  )
}
