import { useEffect, useMemo, useState } from 'react'
import { Activity, BrainCircuit, CheckCircle2, Clock3, History, Radio, RefreshCw, Timer, TrendingDown, TrendingUp, Zap } from 'lucide-react'
import api from '../api/client.js'
import { formatDateTime } from '../utils/dates.js'
import { usePageHeader } from '../PageHeaderContext.jsx'

const fmt = (value, digits = 2) => value == null || Number.isNaN(Number(value)) ? '—' : Number(value).toFixed(digits)
const WINDOWS = ['24h', '48h', '7d', '30d']
const WINDOW_LABELS = { '24h': '24 hours', '48h': '48 hours', '7d': '7 days', '30d': '30 days' }
const WINDOW_STEPS = { '24h': '24 hourly', '48h': '48 hourly', '7d': '28 × 6-hour', '30d': '30 daily' }

function Badge({ children, tone = 'neutral' }) { return <span className={'badge ' + tone}>{children}</span> }

function SeriesChart({ actual = [], forecast = [] }) {
  const history = actual.slice(-32).map(Number).filter(Number.isFinite)
  const future = forecast.slice(0, 48).map(Number).filter(Number.isFinite)
  const values = [...history, ...future]
  if (!values.length) return <div className="empty-state">No telemetry or forecast values available.</div>
  const min = Math.min(...values), max = Math.max(...values), range = max - min || 1
  const width = 820, height = 220
  const point = (value, index, count) => `${(index / Math.max(count - 1, 1)) * width},${height - 16 - ((value - min) / range) * (height - 32)}`
  const all = history.length + future.length
  const actualPoints = history.map((v, i) => point(v, i, all)).join(' ')
  const forecastPoints = future.map((v, i) => point(v, history.length + i, all)).join(' ')
  const split = ((history.length - 1) / Math.max(all - 1, 1)) * width
  return <div style={{overflowX:'auto',background:'var(--panel-raised)',border:'1px solid var(--border)',borderRadius:10,padding:10}}>
    <svg viewBox={`0 0 ${width} ${height}`} width="100%" height="220" role="img" aria-label="Observed telemetry and saved forecast">
      <line x1="0" y1="60" x2={width} y2="60" stroke="var(--border)"/><line x1="0" y1="110" x2={width} y2="110" stroke="var(--border)"/><line x1="0" y1="160" x2={width} y2="160" stroke="var(--border)"/>
      <line x1={split} y1="0" x2={split} y2={height} stroke="var(--text-faint)" strokeDasharray="5 5"/>
      {actualPoints && <polyline fill="none" stroke="var(--accent)" strokeWidth="3" points={actualPoints}/>} {forecastPoints && <polyline fill="none" stroke="var(--warning)" strokeWidth="3" strokeDasharray="7 5" points={forecastPoints}/>} 
      <text x="8" y="18" fill="var(--text-faint)" fontSize="11">observed</text><text x={Math.min(split + 8, width - 100)} y="18" fill="var(--warning)" fontSize="11">saved forecast</text>
    </svg>
    <div style={{display:'flex',justifyContent:'space-between',fontSize:10,color:'var(--text-faint)'}}><span>Telemetry history</span><span>Now → predicted future</span></div>
  </div>
}

function WindowCard({ windowName, run, onRun, busy }) {
  const available = !!run?.available
  return <div className="stat-tile" style={{minHeight:145}}>
    <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',gap:8}}><div className="stat-label"><Clock3 size={13}/> {WINDOW_LABELS[windowName]}</div><Badge tone={available ? 'healthy' : 'warning'}>{available ? 'Forecasted' : 'Waiting'}</Badge></div>
    {available ? <><div className="stat-value" style={{fontSize:20,marginTop:8}}>{fmt(run.end_prediction)}</div><div style={{fontSize:11,color:'var(--text-faint)'}}>endpoint · {run.trend || '—'} · {WINDOW_STEPS[windowName]}</div><div style={{fontSize:10,color:'var(--text-faint)',marginTop:5}}>saved {formatDateTime(run.created_at)}</div></> : <div style={{fontSize:12,color:'var(--text-faint)',marginTop:12}}>{run?.reason || 'Waiting for enough telemetry.'}</div>}
    <button className="btn secondary" style={{marginTop:10,padding:'5px 9px'}} disabled={busy} onClick={() => onRun(windowName)}>{busy ? <><RefreshCw size={12}/> Running…</> : <><Zap size={12}/> Run {windowName}</>}</button>
  </div>
}

export default function PredictionCenter() {
  usePageHeader('AI Monitoring / Model Lab')
  const [lab,setLab]=useState(null), [machineId,setMachineId]=useState(''), [readingType,setReadingType]=useState('temperature'), [model,setModel]=useState('chronos-bolt-tiny'), [horizon,setHorizon]=useState(12)
  const [latest,setLatest]=useState(null), [history,setHistory]=useState([]), [historyWindow,setHistoryWindow]=useState('short'), [actual,setActual]=useState([]), [status,setStatus]=useState(null), [windows,setWindows]=useState(null), [fleetWindows,setFleetWindows]=useState(null)
  const [busy,setBusy]=useState(false), [windowBusy,setWindowBusy]=useState(''), [loading,setLoading]=useState(true), [error,setError]=useState(null), [feedback,setFeedback]=useState(null)
  const machines=lab?.fleet?.machines||[]
  const selectedMachine=useMemo(()=>machines.find(m=>String(m.machine_id)===String(machineId)),[machines,machineId])

  const load=async(preserve=true)=>{
    try{
      const labResult=await api.get('/api/analytics/model-lab'); setLab(labResult)
      const id=machineId||String(labResult?.fleet?.machines?.[0]?.machine_id||''); if(!machineId&&id)setMachineId(id); if(!id)return
      const historyQuery=historyWindow==='short'
        ? `/api/predictions/machines/${id}/history?reading_type=${encodeURIComponent(readingType)}&model=${encodeURIComponent(model)}&horizon=${horizon}&limit=50`
        : `/api/predictions/machines/${id}/history?reading_type=${encodeURIComponent(readingType)}&model=${encodeURIComponent(model)}&forecast_window=${historyWindow}&limit=50`
      const [s,h,readings,w,fw]=await Promise.all([
        api.get(`/api/predictions/machines/${id}/status?reading_type=${encodeURIComponent(readingType)}&model=${encodeURIComponent(model)}&horizon=${horizon}`),
        api.get(historyQuery), api.get(`/api/machines/${id}/readings?limit=64`),
        api.get(`/api/predictions/machines/${id}/windows?reading_type=${encodeURIComponent(readingType)}&model=${encodeURIComponent(model)}`),
        api.get(`/api/predictions/fleet/windows?reading_type=${encodeURIComponent(readingType)}&model=${encodeURIComponent(model)}`),
      ])
      setStatus(s); setHistory(h?.runs||[]); setWindows(w?.windows||null); setFleetWindows(fw||null)
      setActual((readings||[]).filter(r=>r.reading_type===readingType).sort((a,b)=>new Date(a.recorded_at)-new Date(b.recorded_at)).map(r=>Number(r.value)).filter(Number.isFinite).slice(-32))
      if(!preserve||!latest)setLatest(h?.runs?.[0]||null)
      setError(null)
    }catch(e){setError(e?.message||'Prediction center failed to load.')}finally{setLoading(false)}
  }
  useEffect(()=>{load(false)},[machineId,readingType,model,horizon,historyWindow])
  useEffect(()=>{const t=window.setInterval(()=>load(true),30000);return()=>window.clearInterval(t)},[machineId,readingType,model,horizon,historyWindow])

  const runNow=async()=>{
    if(!machineId)return; setBusy(true); setError(null); setFeedback(null)
    try{const result=await api.get(`/api/predictions/machines/${machineId}/forecast?reading_type=${encodeURIComponent(readingType)}&model=${encodeURIComponent(model)}&horizon=${horizon}`);setLatest(result);setFeedback(result?.available?{tone:'healthy',text:`Prediction saved · ${result.model} · ${horizon} steps · ${formatDateTime(result.created_at)}`}: {tone:'warning',text:result?.reason||'Prediction was not generated.'});await load(true)}catch(e){setError(e?.message||'Prediction request failed.')}finally{setBusy(false)}
  }
  const runWindow=async(windowName)=>{
    if(!machineId)return; setWindowBusy(windowName); setError(null); setFeedback(null)
    try{const result=await api.get(`/api/predictions/machines/${machineId}/windows/run?window=${windowName}&reading_type=${encodeURIComponent(readingType)}&model=${encodeURIComponent(model)}`);setLatest(result);setFeedback(result?.available?{tone:'healthy',text:`${WINDOW_LABELS[windowName]} forecast saved · ${result.horizon} steps · ${formatDateTime(result.created_at)}`}:{tone:'warning',text:result?.reason||'Forecast was not generated.'});setHistoryWindow(windowName);await load(true)}catch(e){setError(e?.message||`${windowName} forecast failed.`)}finally{setWindowBusy('')}
  }

  const prediction=latest?.forecast||[], lastActual=actual.length?actual[actual.length-1]:null, endDelta=latest?.end_prediction==null||lastActual==null?null:latest.end_prediction-lastActual
  if(loading&&!lab)return <div className="panel"><div className="panel-body">Loading prediction system…</div></div>

  return <>
    <div className="panel section-gap"><div className="panel-header"><span className="panel-title">Prediction Center</span><Badge tone={status?.telemetry_active?'healthy':'warning'}>{status?.telemetry_active?'Telemetry active':'Waiting for telemetry'}</Badge></div><div className="panel-body"><p style={{color:'var(--text-dim)',fontSize:13,lineHeight:1.6,margin:0}}>Forecasts are durable records tied to real telemetry. Automatic inference only runs after new sensor data passes freshness, minimum-history and deduplication checks. Manual runs are shown immediately below the controls.</p></div></div>

    <div className="panel section-gap" style={{border:'1px solid var(--accent)'}}><div className="panel-header"><span className="panel-title">Forecast configuration</span><Badge>Automatic + manual</Badge></div><div className="panel-body">
      <div className="grid-2" style={{marginBottom:12}}>
        <label>Machine<select value={machineId} onChange={e=>{setMachineId(e.target.value);setLatest(null);setFeedback(null)}}>{machines.map(m=><option key={m.machine_id} value={m.machine_id}>{m.machine_name} · {m.category||'other'}</option>)}</select></label>
        <label>Signal<select value={readingType} onChange={e=>{setReadingType(e.target.value);setLatest(null);setFeedback(null)}}><option value="temperature">Temperature</option><option value="vibration">Vibration</option><option value="current">Motor Current</option><option value="load">Machine Load</option><option value="humidity">Humidity</option></select></label>
        <label>Time-series model<select value={model} onChange={e=>{setModel(e.target.value);setLatest(null);setFeedback(null)}}><option value="chronos-bolt-tiny">Chronos-Bolt-Tiny</option><option value="timer">Timer</option></select></label>
        <label>Short forecast<select value={horizon} onChange={e=>setHorizon(Number(e.target.value))}><option value="6">6 steps</option><option value="12">12 steps</option><option value="24">24 steps</option></select></label>
      </div>
      <div className="chip-row" style={{alignItems:'center'}}><button className="btn" onClick={runNow} disabled={busy||!machineId}>{busy?<><RefreshCw size={14}/> Running model…</>:<><BrainCircuit size={14}/> Run short forecast</>}</button><span style={{fontSize:11,color:'var(--text-faint)'}}><Clock3 size={12} style={{verticalAlign:'-2px'}}/> {Math.round((status?.interval_seconds||300)/60)} min cadence after new telemetry</span><span style={{fontSize:11,color:'var(--text-faint)'}}><Radio size={12} style={{verticalAlign:'-2px'}}/> {status?.telemetry_active?'New telemetry can trigger forecasting':'No recent telemetry: no automatic inference'}</span></div>
      {feedback&&<div style={{marginTop:12,padding:'10px 12px',borderRadius:8,border:'1px solid var(--border)',background:'var(--panel-raised)',fontSize:12,display:'flex',alignItems:'center',gap:8}}><CheckCircle2 size={15}/><span>{feedback.text}</span></div>}
    </div></div>

    {error&&<div className="panel section-gap"><div className="panel-body" style={{color:'var(--critical)',fontSize:12}}>{error}</div></div>}

    <div className="panel section-gap"><div className="panel-header"><span className="panel-title">Machine forecast horizons · {selectedMachine?.machine_name||'Machine'}</span><Badge>Saved per machine</Badge></div><div className="panel-body"><div className="stat-grid">{WINDOWS.map(name=><WindowCard key={name} windowName={name} run={windows?.[name]} onRun={runWindow} busy={windowBusy===name}/>)}</div><div style={{marginTop:12,fontSize:11,color:'var(--text-faint)'}}>24h = 24 hourly steps · 48h = 48 hourly steps · 7d = 28 six-hour steps · 30d = 30 daily steps. These are sensor-value trajectories, not failure probabilities.</div></div></div>

    <div className="panel section-gap"><div className="panel-header"><span className="panel-title">Fleet forecast matrix</span><span className="badge neutral">{fleetWindows?.machines?.length||0} machines</span></div><div className="panel-body"><div style={{overflowX:'auto'}}><table><thead><tr><th>Machine</th><th>Telemetry</th><th>24h</th><th>48h</th><th>7d</th><th>30d</th></tr></thead><tbody>{(fleetWindows?.machines||[]).map(machine=><tr key={machine.machine_id}><td><button className="btn secondary" style={{padding:'4px 8px'}} onClick={()=>{setMachineId(String(machine.machine_id));setLatest(null)}}>{machine.machine_name}</button></td><td>{machine.telemetry_at?formatDateTime(machine.telemetry_at):<Badge tone="warning">No telemetry</Badge>}</td>{WINDOWS.map(name=>{const run=machine.windows?.[name];return <td key={name}>{run?.available?<><b className="mono">{fmt(run.end_prediction)}</b><div style={{fontSize:10,color:'var(--text-faint)'}}>{run.trend||'—'}</div></>:<span style={{fontSize:10,color:'var(--text-faint)'}}>waiting</span>}</td>})}</tr>)}{!fleetWindows?.machines?.length&&<tr><td colSpan="6" style={{textAlign:'center',padding:20,color:'var(--text-faint)'}}>No forecast data yet.</td></tr>}</tbody></table></div><div style={{marginTop:10,fontSize:11,color:'var(--text-faint)'}}>Each machine has independent saved forecast records. Machines without fresh telemetry stay idle and consume no automatic ML inference.</div></div></div>

    <div className="stat-grid section-gap"><div className="stat-tile"><div className="stat-label"><BrainCircuit size={14}/> MODEL</div><div className="stat-value" style={{fontSize:18}}>{latest?.model||model}</div><div style={{fontSize:11,color:'var(--text-faint)'}}>{selectedMachine?.machine_name||'Machine'}</div></div><div className="stat-tile"><div className="stat-label"><Activity size={14}/> NEXT</div><div className="stat-value">{fmt(latest?.next_prediction)}</div><div style={{fontSize:11,color:'var(--text-faint)'}}>t+1 · {readingType}</div></div><div className="stat-tile"><div className="stat-label"><TrendingUp size={14}/> END</div><div className="stat-value">{fmt(latest?.end_prediction)}</div><div style={{fontSize:11,color:'var(--text-faint)'}}>{latest?.trend||'No forecast yet'}</div></div><div className="stat-tile"><div className="stat-label"><Radio size={14}/> TELEMETRY</div><div className="stat-value" style={{fontSize:18}}>{status?.telemetry_active?'Active':'Idle'}</div><div style={{fontSize:11,color:'var(--text-faint)'}}>{status?.latest_telemetry_at?formatDateTime(status.latest_telemetry_at):'No reading'}</div></div></div>

    {latest?.available&&<div className="panel section-gap"><div className="panel-header"><span className="panel-title">Latest saved prediction</span><Badge tone={latest.trigger==='automatic'?'healthy':'neutral'}>{latest.trigger}</Badge></div><div className="panel-body"><SeriesChart actual={actual} forecast={prediction}/><div style={{display:'grid',gridTemplateColumns:'repeat(4,minmax(0,1fr))',gap:8,marginTop:12}}>{prediction.map((value,i)=><div key={i} style={{padding:9,borderRadius:7,background:'var(--panel-raised)',border:'1px solid var(--border)'}}><div className="mono" style={{fontWeight:700}}>{fmt(value)}</div><div style={{fontSize:10,color:'var(--text-faint)',marginTop:3}}>t+{i+1}</div></div>)}</div><div style={{marginTop:12,fontSize:12,color:'var(--text-dim)'}}>Current observed value: <b>{fmt(lastActual)}</b> · forecast endpoint delta: <b>{endDelta==null?'—':`${endDelta>=0?'+':''}${fmt(endDelta)}`}</b>. This is a signal forecast, not a failure probability.</div></div></div>}

    <div className="panel section-gap"><div className="panel-header"><span className="panel-title"><History size={15} style={{verticalAlign:'-3px',marginRight:6}}/>Prediction history</span><div style={{display:'flex',gap:8,alignItems:'center'}}><select value={historyWindow} onChange={e=>setHistoryWindow(e.target.value)}><option value="short">Short forecast · {horizon} steps</option>{WINDOWS.map(w=><option key={w} value={w}>{WINDOW_LABELS[w]}</option>)}</select><span className="badge neutral">{history.length} saved</span></div></div><div className="panel-body"><div style={{fontSize:11,color:'var(--text-faint)',marginBottom:10}}>History is stored in the database. Switching the filter shows previous runs for that machine, signal, model and horizon/window instead of only the newest record.</div><div style={{overflowX:'auto'}}><table><thead><tr><th>Created</th><th>Trigger</th><th>Input end</th><th>Steps</th><th>Next</th><th>Endpoint</th><th>Trend</th></tr></thead><tbody>{history.length?history.map(run=><tr key={run.run_id}><td>{formatDateTime(run.created_at)}</td><td>{run.trigger}</td><td>{formatDateTime(run.input_ended_at)}</td><td>{run.horizon}</td><td className="mono">{fmt(run.next_prediction)}</td><td className="mono">{fmt(run.end_prediction)}</td><td>{run.trend==='Increasing'?<TrendingUp size={14}/>:run.trend==='Decreasing'?<TrendingDown size={14}/>: 'Stable'}</td></tr>):<tr><td colSpan="7" style={{textAlign:'center',padding:20,color:'var(--text-faint)'}}>No saved forecasts for this selection yet.</td></tr>}</tbody></table></div></div></div>

    <div className="grid-2 section-gap"><div className="panel"><div className="panel-header"><span className="panel-title">Automatic forecasting</span><RefreshCw size={15}/></div><div className="panel-body" style={{fontSize:12,color:'var(--text-dim)',lineHeight:1.6}}><b>It is telemetry-driven, not a blind timer.</b> A new sensor reading invokes the coordinator, which checks minimum history, freshness, cadence and duplicate reservations. If telemetry stops, no new prediction calls are made. Long horizons are resampled before inference.</div></div><div className="panel"><div className="panel-header"><span className="panel-title">Model roles</span><Timer size={15}/></div><div className="panel-body" style={{fontSize:12,color:'var(--text-dim)',lineHeight:1.6}}><b>Chronos-Bolt-Tiny</b> is the default production model. <b>Timer</b> is the secondary time-series model and now runs through the dedicated ML service. Neither model produces an uncalibrated failure probability.</div></div></div>

    <div className="panel section-gap"><div className="panel-header"><span className="panel-title">Risk Data Readiness</span><span className="badge neutral">Not a signal forecast</span></div><div className="panel-body"><div style={{display:'grid',gap:8}}>{Object.entries(lab?.risk_readiness?.horizons||{}).map(([h,v])=><div key={h} style={{display:'grid',gridTemplateColumns:'55px 1fr 1fr',gap:8,alignItems:'center',fontSize:12}}><span className="mono">{h}</span><span>Labels: <b>{v.complete_labels}</b></span><span>Positive: <b>{v.positive_outcomes}</b> · Negative: <b>{v.negative_outcomes}</b></span></div>)}</div><div style={{marginTop:12,color:'var(--text-faint)',fontSize:11}}>These entries describe whether enough leakage-safe failure outcomes exist for future calibrated risk models. They are not converted into failure probabilities until corresponding models are trained and validated.</div></div></div>
  </>
}
