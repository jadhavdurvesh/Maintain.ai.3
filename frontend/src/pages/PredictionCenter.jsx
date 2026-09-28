import { useEffect, useMemo, useState } from 'react'
import { Activity, BrainCircuit, CheckCircle2, Clock3, History, Radio, RefreshCw, Timer, TrendingDown, TrendingUp } from 'lucide-react'
import api from '../api/client.js'
import { formatDateTime } from '../utils/dates.js'
import { usePageHeader } from '../PageHeaderContext.jsx'

const WINDOWS = ['24h', '48h', '7d', '30d']
const WINDOW_LABELS = { '24h': '24 hours', '48h': '48 hours', '7d': '7 days', '30d': '30 days' }
const WINDOW_STEPS = { '24h': '24 hourly steps', '48h': '48 hourly steps', '7d': '28 × 6-hour steps', '30d': '30 daily steps' }
const MODEL_MIN_SAMPLES = { 'chronos-bolt-tiny': 16, timer: 16 }

const fmt = (value, digits = 2) => value == null || Number.isNaN(Number(value)) ? '—' : Number(value).toFixed(digits)

function Badge({ children, tone = 'neutral' }) {
  return <span className={'badge ' + tone}>{children}</span>
}

function ForecastChart({ actual = [], forecast = [] }) {
  const history = actual.slice(-32).map(Number).filter(Number.isFinite)
  const future = forecast.slice(0, 48).map(Number).filter(Number.isFinite)
  const values = [...history, ...future]
  if (!values.length) return <div className="empty-state">No telemetry or forecast values available.</div>
  const min = Math.min(...values)
  const max = Math.max(...values)
  const range = max - min || 1
  const width = 820
  const height = 250
  const allCount = history.length + future.length
  const point = (value, index) => `${(index / Math.max(allCount - 1, 1)) * width},${height - 22 - ((value - min) / range) * (height - 42)}`
  const actualPoints = history.map((value, index) => point(value, index)).join(' ')
  const forecastPoints = future.map((value, index) => point(value, history.length + index)).join(' ')
  const split = ((history.length - 1) / Math.max(allCount - 1, 1)) * width
  return <div style={{background:'var(--panel-raised)',border:'1px solid var(--border)',borderRadius:12,padding:12}}>
    <svg viewBox={`0 0 ${width} ${height}`} width="100%" height="250" role="img" aria-label="Observed telemetry and saved forecast">
      {[64, 122, 180].map(y => <line key={y} x1="0" y1={y} x2={width} y2={y} stroke="var(--border)" />)}
      <line x1={split} y1="0" x2={split} y2={height} stroke="var(--text-faint)" strokeDasharray="5 5" />
      {actualPoints && <polyline fill="none" stroke="var(--accent)" strokeWidth="3.5" strokeLinejoin="round" strokeLinecap="round" points={actualPoints} />}
      {forecastPoints && <polyline fill="none" stroke="var(--warning)" strokeWidth="3.5" strokeDasharray="8 6" strokeLinejoin="round" strokeLinecap="round" points={forecastPoints} />}
      <text x="8" y="18" fill="var(--text-faint)" fontSize="11">actual</text>
      <text x={Math.min(split + 8, width - 115)} y="18" fill="var(--warning)" fontSize="11">forecast</text>
    </svg>
    <div style={{display:'flex',justifyContent:'space-between',fontSize:10,color:'var(--text-faint)'}}><span>Older telemetry</span><span>Now → predicted future</span></div>
  </div>
}

function PredictionSummary({ run, actual }) {
  const forecast = (run?.forecast || []).map(Number).filter(Number.isFinite)
  const history = (actual || []).map(Number).filter(Number.isFinite)
  if (!forecast.length) return null
  const latest = history.at(-1)
  const first = forecast[0]
  const last = forecast.at(-1)
  const firstDelta = latest == null ? null : first - latest
  const totalDelta = latest == null ? null : last - latest
  const direction = totalDelta == null || Math.abs(totalDelta) < 1e-6 ? 'Stable' : totalDelta > 0 ? 'Increasing' : 'Decreasing'
  return <div className="stat-grid" style={{marginTop:12}}>
    <div className="stat-tile"><div className="stat-label"><Activity size={14}/> NEXT PREDICTION</div><div className="stat-value" style={{fontSize:22}}>{fmt(first)}</div><div style={{fontSize:11,color:'var(--text-faint)'}}>t+1</div></div>
    <div className="stat-tile"><div className="stat-label"><TrendingUp size={14}/> END OF HORIZON</div><div className="stat-value" style={{fontSize:22}}>{fmt(last)}</div><div style={{fontSize:11,color:'var(--text-faint)'}}>t+{forecast.length}</div></div>
    <div className="stat-tile"><div className="stat-label"><TrendingDown size={14}/> EXPECTED TREND</div><div className="stat-value" style={{fontSize:22}}>{direction}</div><div style={{fontSize:11,color:'var(--text-faint)'}}>{totalDelta == null ? 'No baseline' : `${totalDelta >= 0 ? '+' : ''}${fmt(totalDelta)} vs latest`}</div></div>
    <div className="stat-tile"><div className="stat-label"><BrainCircuit size={14}/> MODEL OUTPUT</div><div className="stat-value" style={{fontSize:22}}>{fmt(firstDelta)}</div><div style={{fontSize:11,color:'var(--text-faint)'}}>first step vs latest</div></div>
  </div>
}

function HorizonCard({ name, run, selected, onSelect }) {
  const available = !!run?.available
  const running = run?.status === 'running' || !!run?.running
  return <button type="button" className="stat-tile" onClick={() => available && onSelect(name)} disabled={!available} style={{minHeight:150,textAlign:'left',cursor:available?'pointer':'default',border:selected?'1px solid var(--accent)':'1px solid var(--border)',opacity:available?1:.82}}>
    <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',gap:8}}><div className="stat-label"><Clock3 size={13}/> {WINDOW_LABELS[name]}</div><Badge tone={available?'healthy':running?'neutral':'warning'}>{available?'Forecasted':running?'Running':'Waiting'}</Badge></div>
    {available ? <><div className="stat-value" style={{fontSize:21,marginTop:10}}>{fmt(run.end_prediction)}</div><div style={{fontSize:11,color:'var(--text-faint)'}}>endpoint · {run.trend || 'Stable'} · {WINDOW_STEPS[name]}</div><div style={{fontSize:10,color:'var(--text-faint)',marginTop:7}}>saved {formatDateTime(run.created_at)} · click to view</div></> : <><div style={{fontSize:12,color:'var(--text-faint)',marginTop:12,minHeight:36}}>{run?.reason || 'Waiting for automatic telemetry.'}</div><div style={{fontSize:10,color:'var(--text-faint)',marginTop:8}}>Generated automatically from telemetry</div></>}
  </button>
}

export default function PredictionCenter() {
  usePageHeader('AI Monitoring / Model Lab')
  const [lab, setLab] = useState(null)
  const [machineId, setMachineId] = useState('')
  const [readingType, setReadingType] = useState('temperature')
  const [model, setModel] = useState('chronos-bolt-tiny')
  const [horizon, setHorizon] = useState(12)
  const [latest, setLatest] = useState(null)
  const [history, setHistory] = useState([])
  const [historyWindow, setHistoryWindow] = useState('short')
  const [actual, setActual] = useState([])
  const [status, setStatus] = useState(null)
  const [windows, setWindows] = useState(null)
  const [fleetWindows, setFleetWindows] = useState(null)
  const [busy, setBusy] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [feedback, setFeedback] = useState(null)

  const machines = lab?.fleet?.machines || []
  const selectedMachine = useMemo(() => machines.find(m => String(m.machine_id) === String(machineId)), [machines, machineId])
  const sampleCount = Number(status?.sample_count || 0)
  const telemetryFresh = !!status?.telemetry_active
  const minimumSamples = MODEL_MIN_SAMPLES[model] || 16
  const canShortRun = !!machineId && sampleCount >= minimumSamples
  const telemetryLabel = telemetryFresh ? 'Telemetry active' : sampleCount >= minimumSamples ? 'Telemetry stale · manual replay available' : `Need ${minimumSamples} samples`

  const load = async ({ preserve = true } = {}) => {
    try {
      const labResult = await api.get('/api/analytics/model-lab')
      setLab(labResult)
      const id = machineId || String(labResult?.fleet?.machines?.[0]?.machine_id || '')
      if (!machineId && id) setMachineId(id)
      if (!id) return
      const historyQuery = historyWindow === 'short'
        ? `/api/predictions/machines/${id}/history?reading_type=${encodeURIComponent(readingType)}&model=${encodeURIComponent(model)}&horizon=${horizon}&limit=50`
        : `/api/predictions/machines/${id}/history?reading_type=${encodeURIComponent(readingType)}&model=${encodeURIComponent(model)}&forecast_window=${historyWindow}&limit=50`
      const [s, h, readings, w, fw] = await Promise.all([
        api.get(`/api/predictions/machines/${id}/status?reading_type=${encodeURIComponent(readingType)}&model=${encodeURIComponent(model)}&horizon=${horizon}`),
        api.get(historyQuery),
        api.get(`/api/machines/${id}/readings?limit=64`),
        api.get(`/api/predictions/machines/${id}/windows?reading_type=${encodeURIComponent(readingType)}&model=${encodeURIComponent(model)}`),
        api.get(`/api/predictions/fleet/windows?reading_type=${encodeURIComponent(readingType)}&model=${encodeURIComponent(model)}`),
      ])
      const runs = h?.runs || []
      const persisted = s?.latest_run?.available ? s.latest_run : null
      setStatus(s); setHistory(runs); setWindows(w?.windows || null); setFleetWindows(fw || null)
      setActual((readings || []).filter(r => r.reading_type === readingType).sort((a,b) => new Date(a.recorded_at) - new Date(b.recorded_at)).map(r => Number(r.value)).filter(Number.isFinite).slice(-32))
      if (!preserve) setLatest(runs[0] || persisted || null)
      else setLatest(previous => {
        if (previous?.available && String(previous.machine_id) === String(id) && previous.reading_type === readingType && previous.model === model) return previous
        return runs[0] || persisted || previous || null
      })
      setError(null)
    } catch (e) { setError(e?.message || 'Prediction center failed to load.') }
    finally { setLoading(false) }
  }

  useEffect(() => { load({ preserve: false }) }, [machineId, readingType, model, horizon, historyWindow])
  useEffect(() => { const timer = window.setInterval(() => load({ preserve: true }), 30000); return () => window.clearInterval(timer) }, [machineId, readingType, model, horizon, historyWindow])

  const selectMachine = value => { setMachineId(value); setFeedback(null) }
  const selectSignal = value => { setReadingType(value); setFeedback(null) }
  const selectModel = value => { setModel(value); setFeedback(null) }

  const runNow = async () => {
    if (!machineId || sampleCount < minimumSamples) return
    setBusy(true); setError(null); setFeedback(null)
    try {
      const result = await api.get(`/api/predictions/machines/${machineId}/forecast?reading_type=${encodeURIComponent(readingType)}&model=${encodeURIComponent(model)}&horizon=${horizon}`)
      if (result?.available) setLatest(result)
      setFeedback({ tone: result?.available ? 'healthy' : 'warning', text: result?.available ? `Prediction saved · ${result.model} · ${horizon} steps · ${formatDateTime(result.created_at)}` : result?.reason || 'Prediction was not generated.' })
      await load({ preserve: true })
    } catch (e) { setError(e?.message || 'Prediction request failed.') }
    finally { setBusy(false) }
  }

  const showWindow = name => {
    const run = windows?.[name]
    if (!run?.available) return
    setHistoryWindow(name); setLatest(run)
    setFeedback({ tone: 'healthy', text: `${WINDOW_LABELS[name]} forecast loaded from saved prediction · ${run.horizon} steps` })
  }

  const prediction = latest?.forecast || []
  const lastActual = actual.at(-1)
  const endDelta = latest?.end_prediction == null || lastActual == null ? null : latest.end_prediction - lastActual

  if (loading && !lab) return <div className="panel"><div className="panel-body">Loading prediction system…</div></div>

  return <>
    <div className="panel section-gap"><div className="panel-header"><span className="panel-title">Prediction Center</span><div style={{display:'flex',gap:8,alignItems:'center'}}><Badge tone={telemetryFresh?'healthy':'warning'}>{telemetryLabel}</Badge><span className="badge neutral">{sampleCount} samples</span></div></div><div className="panel-body" style={{paddingTop:8,paddingBottom:10}}><span style={{color:'var(--text-dim)',fontSize:12}}>Historical telemetry → selected forecasting model → saved future signal trajectory. Forecasts are signal estimates, not failure probabilities.</span></div></div>

    <div className="panel section-gap" style={{border:'1px solid var(--accent)',boxShadow:'0 0 28px rgba(0,200,255,.07)'}}><div className="panel-header"><span className="panel-title">Forecast configuration</span><Badge>{model === 'timer' ? 'Timer-Lite · memory-safe · 16 samples' : 'Chronos-Bolt-Tiny · production · 16 samples'}</Badge></div><div className="panel-body">
      <div className="grid-2" style={{marginBottom:12}}>
        <label>Machine<select value={machineId} onChange={e => selectMachine(e.target.value)}>{machines.map(m => <option key={m.machine_id} value={m.machine_id}>{m.machine_name} · {m.category || 'other'}</option>)}</select></label>
        <label>Signal<select value={readingType} onChange={e => selectSignal(e.target.value)}><option value="temperature">Temperature</option><option value="vibration">Vibration</option><option value="current">Motor Current</option><option value="load">Machine Load</option><option value="humidity">Humidity</option></select></label>
        <label>Forecast model<select value={model} onChange={e => selectModel(e.target.value)}><option value="chronos-bolt-tiny">Chronos-Bolt-Tiny</option><option value="timer">Timer-Lite</option></select></label>
        <label>Prediction horizon<select value={horizon} onChange={e => setHorizon(Number(e.target.value))}><option value="6">6 steps</option><option value="12">12 steps</option><option value="24">24 steps</option></select></label>
      </div>
      <div className="chip-row" style={{alignItems:'center'}}><button className="btn" onClick={runNow} disabled={busy || !canShortRun}>{busy ? <><RefreshCw size={14}/> Running model…</> : <><BrainCircuit size={14}/> Run prediction</>}</button><span style={{fontSize:11,color:'var(--text-faint)'}}><Clock3 size={12} style={{verticalAlign:'-2px'}}/> Automatic cadence: {Math.round((status?.interval_seconds || 300) / 60)} min after new telemetry</span><span style={{fontSize:11,color:telemetryFresh?'var(--text-faint)':'var(--warning)'}}><Radio size={12} style={{verticalAlign:'-2px'}}/> {telemetryFresh ? 'Live telemetry can trigger automatic forecasts' : `Manual replay available · ${sampleCount}/${minimumSamples} samples`}</span></div>
      {feedback && <div style={{marginTop:12,padding:'10px 12px',borderRadius:8,border:'1px solid var(--border)',background:'var(--panel-raised)',fontSize:12,display:'flex',alignItems:'center',gap:8}}><CheckCircle2 size={15}/><span>{feedback.text}</span></div>}
    </div></div>

    {error && <div className="panel section-gap"><div className="panel-body" style={{color:'var(--critical)',fontSize:12}}>{error}</div></div>}

    {latest?.available && <div className="panel section-gap"><div className="panel-header"><span className="panel-title">Saved prediction · {selectedMachine?.machine_name || 'Machine'}</span><div style={{display:'flex',gap:8,alignItems:'center'}}><Badge tone="healthy">Saved</Badge><span className="badge neutral">{latest.horizon} steps</span></div></div><div className="panel-body">
      <PredictionSummary run={latest} actual={actual}/><div style={{marginTop:14}}><ForecastChart actual={actual} forecast={prediction}/></div>
      <div style={{display:'grid',gridTemplateColumns:'repeat(4,minmax(0,1fr))',gap:8,marginTop:12}}>{prediction.slice(0,12).map((value,i)=><div key={i} style={{padding:9,borderRadius:7,background:'var(--panel-raised)',border:'1px solid var(--border)'}}><div className="mono" style={{fontWeight:700}}>{fmt(value)}</div><div style={{fontSize:10,color:'var(--text-faint)',marginTop:3}}>t+{i+1}</div></div>)}</div>
      <div style={{marginTop:12,fontSize:12,color:'var(--text-dim)'}}>Current observed value: <b>{fmt(lastActual)}</b> · forecast endpoint delta: <b>{endDelta == null ? '—' : `${endDelta >= 0 ? '+' : ''}${fmt(endDelta)}`}</b> · model: <b className="mono">{latest.model}</b>.</div>
      <div style={{marginTop:12,padding:12,borderRadius:8,background:'var(--panel-raised)',fontSize:12,color:'var(--text-dim)'}}><b>How to read this:</b> the solid line is recent observed telemetry; the dashed line is the saved model forecast. A rising or falling signal is not, by itself, a failure diagnosis.</div>
    </div></div>}

    <div className="panel section-gap"><div className="panel-header"><span className="panel-title">Automatic forecast horizons · {selectedMachine?.machine_name || 'Machine'}</span><Badge>Telemetry-driven · saved automatically</Badge></div><div className="panel-body">
      <div className="stat-grid">{WINDOWS.map(name => <HorizonCard key={name} name={name} run={windows?.[name]} selected={latest?.forecast_window === name} onSelect={showWindow}/>)}</div>
      <div style={{marginTop:12,fontSize:11,color:'var(--text-faint)',lineHeight:1.5}}>These four horizons are generated by the backend after sensor telemetry arrives. There are no manual horizon buttons. Existing saved forecasts remain in the database and can be reopened for the same machine, signal and model.</div>
    </div></div>

    <div className="panel section-gap"><div className="panel-header"><span className="panel-title">Fleet forecast matrix</span><span className="badge neutral">{fleetWindows?.machines?.length || 0} machines</span></div><div className="panel-body"><div style={{overflowX:'auto'}}><table><thead><tr><th>Machine</th><th>Telemetry</th>{WINDOWS.map(name => <th key={name}>{WINDOW_LABELS[name]}</th>)}</tr></thead><tbody>{(fleetWindows?.machines || []).map(machine => <tr key={machine.machine_id}><td><button className="btn secondary" style={{padding:'4px 8px'}} onClick={() => selectMachine(String(machine.machine_id))}>{machine.machine_name}</button></td><td>{machine.telemetry_at ? formatDateTime(machine.telemetry_at) : <Badge tone="warning">No telemetry</Badge>}</td>{WINDOWS.map(name => { const run = machine.windows?.[name]; return <td key={name}>{run?.available ? <><b className="mono">{fmt(run.end_prediction)}</b><div style={{fontSize:10,color:'var(--text-faint)'}}>{run.trend || 'Stable'}</div></> : <span style={{fontSize:10,color:'var(--text-faint)'}}>waiting</span>}</td> })}</tr>)}{!fleetWindows?.machines?.length && <tr><td colSpan="6" style={{textAlign:'center',padding:20,color:'var(--text-faint)'}}>No forecast data yet.</td></tr>}</tbody></table></div></div></div>

    <div className="panel section-gap"><div className="panel-header"><span className="panel-title"><History size={15} style={{verticalAlign:'-3px',marginRight:6}}/>Prediction history</span><div style={{display:'flex',gap:8,alignItems:'center'}}><select value={historyWindow} onChange={e => setHistoryWindow(e.target.value)}><option value="short">Short forecast · {horizon} steps</option>{WINDOWS.map(w => <option key={w} value={w}>{WINDOW_LABELS[w]}</option>)}</select><span className="badge neutral">{history.length} saved</span></div></div><div className="panel-body"><div style={{fontSize:11,color:'var(--text-faint)',marginBottom:10}}>Saved predictions are persistent. Changing machine, signal, model, horizon or window reloads the corresponding stored run instead of starting from an empty chart.</div><div style={{overflowX:'auto'}}><table><thead><tr><th>Created</th><th>Trigger</th><th>Input end</th><th>Steps</th><th>Next</th><th>Endpoint</th><th>Trend</th></tr></thead><tbody>{history.length ? history.map(run => <tr key={run.run_id}><td>{formatDateTime(run.created_at)}</td><td>{run.trigger}</td><td>{formatDateTime(run.input_ended_at)}</td><td>{run.horizon}</td><td className="mono">{fmt(run.next_prediction)}</td><td className="mono">{fmt(run.end_prediction)}</td><td>{run.trend === 'Increasing' ? <TrendingUp size={14}/> : run.trend === 'Decreasing' ? <TrendingDown size={14}/> : 'Stable'}</td></tr>) : <tr><td colSpan="7" style={{textAlign:'center',padding:20,color:'var(--text-faint)'}}>No saved forecasts for this selection yet.</td></tr>}</tbody></table></div></div></div>

    <div className="grid-2 section-gap"><div className="panel"><div className="panel-header"><span className="panel-title">Automatic forecasting</span><RefreshCw size={15}/></div><div className="panel-body" style={{fontSize:12,color:'var(--text-dim)',lineHeight:1.6}}><b>Telemetry-driven, not a blind timer.</b> New sensor readings schedule forecasts in the backend. Cadence, duplicate reservations, freshness and minimum history are checked before inference. If telemetry stops, automatic inference stops too.</div></div><div className="panel"><div className="panel-header"><span className="panel-title">Model roles</span><Timer size={15}/></div><div className="panel-body" style={{fontSize:12,color:'var(--text-dim)',lineHeight:1.6}}><b>Chronos-Bolt-Tiny</b> is the production default. <b>Timer-Lite</b> is the memory-safe Timer-compatible fallback used on the low-memory ML service; it avoids loading the 84M-parameter Timer checkpoint.</div></div></div>
  </>
}
