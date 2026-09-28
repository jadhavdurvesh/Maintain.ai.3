import { useEffect, useMemo, useState } from 'react'
import { Activity, BrainCircuit, Clock3, History, Radio, RefreshCw, Timer, TrendingDown, TrendingUp } from 'lucide-react'
import api from '../api/client.js'
import { formatDateTime } from '../utils/dates.js'
import { usePageHeader } from '../PageHeaderContext.jsx'

const fmt = (value, digits = 2) => value == null || Number.isNaN(Number(value)) ? '—' : Number(value).toFixed(digits)

function Badge({ children, tone = 'neutral' }) {
  return <span className={'badge ' + tone}>{children}</span>
}

function SeriesChart({ actual = [], forecast = [] }) {
  const history = actual.slice(-32).map(Number).filter(Number.isFinite)
  const future = forecast.slice(0, 24).map(Number).filter(Number.isFinite)
  const values = [...history, ...future]
  if (!values.length) return <div className="empty-state">No telemetry or forecast values available.</div>
  const min = Math.min(...values)
  const max = Math.max(...values)
  const range = max - min || 1
  const width = 820
  const height = 220
  const point = (value, index, count) => `${(index / Math.max(count - 1, 1)) * width},${height - 16 - ((value - min) / range) * (height - 32)}`
  const all = history.length + future.length
  const actualPoints = history.map((v, i) => point(v, i, all)).join(' ')
  const forecastPoints = future.map((v, i) => point(v, history.length + i, all)).join(' ')
  const split = ((history.length - 1) / Math.max(all - 1, 1)) * width
  return <div style={{ overflowX: 'auto', background: 'var(--panel-raised)', border: '1px solid var(--border)', borderRadius: 10, padding: 10 }}>
    <svg viewBox={`0 0 ${width} ${height}`} width="100%" height="220" role="img" aria-label="Observed telemetry and saved forecast">
      <line x1="0" y1="60" x2={width} y2="60" stroke="var(--border)" /><line x1="0" y1="110" x2={width} y2="110" stroke="var(--border)" /><line x1="0" y1="160" x2={width} y2="160" stroke="var(--border)" />
      <line x1={split} y1="0" x2={split} y2={height} stroke="var(--text-faint)" strokeDasharray="5 5" />
      {actualPoints && <polyline fill="none" stroke="var(--accent)" strokeWidth="3" points={actualPoints} />}
      {forecastPoints && <polyline fill="none" stroke="var(--warning)" strokeWidth="3" strokeDasharray="7 5" points={forecastPoints} />}
      <text x="8" y="18" fill="var(--text-faint)" fontSize="11">observed</text>
      <text x={Math.min(split + 8, width - 100)} y="18" fill="var(--warning)" fontSize="11">saved forecast</text>
    </svg>
    <div style={{display:'flex',justifyContent:'space-between',fontSize:10,color:'var(--text-faint)'}}><span>Telemetry history</span><span>Now → predicted future</span></div>
  </div>
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
  const [actual, setActual] = useState([])
  const [status, setStatus] = useState(null)
  const [busy, setBusy] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const machines = lab?.fleet?.machines || []
  const selectedMachine = useMemo(() => machines.find(m => String(m.machine_id) === String(machineId)), [machines, machineId])

  const load = async (preserveResult = true) => {
    try {
      const labResult = await api.get('/api/analytics/model-lab')
      setLab(labResult)
      const id = machineId || String(labResult?.fleet?.machines?.[0]?.machine_id || '')
      if (!machineId && id) setMachineId(id)
      if (!id) return
      const [s, h, readings] = await Promise.all([
        api.get(`/api/predictions/machines/${id}/status?reading_type=${encodeURIComponent(readingType)}&model=${encodeURIComponent(model)}&horizon=${horizon}`),
        api.get(`/api/predictions/machines/${id}/history?reading_type=${encodeURIComponent(readingType)}&model=${encodeURIComponent(model)}&horizon=${horizon}&limit=20`),
        api.get(`/api/machines/${id}/readings?limit=64`),
      ])
      setStatus(s)
      setHistory(h?.runs || [])
      setActual((readings || []).filter(r => r.reading_type === readingType).sort((a,b) => new Date(a.recorded_at) - new Date(b.recorded_at)).map(r => Number(r.value)).filter(Number.isFinite).slice(-32))
      if (!preserveResult || !latest) setLatest(h?.runs?.[0] || null)
      setError(null)
    } catch (e) {
      setError(e?.message || 'Prediction center failed to load.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load(false) }, [machineId, readingType, model, horizon])
  useEffect(() => {
    const timer = window.setInterval(() => load(true), 30000)
    return () => window.clearInterval(timer)
  }, [machineId, readingType, model, horizon])

  const runNow = async () => {
    if (!machineId) return
    setBusy(true); setError(null)
    try {
      const result = await api.get(`/api/predictions/machines/${machineId}/forecast?reading_type=${encodeURIComponent(readingType)}&model=${encodeURIComponent(model)}&horizon=${horizon}`)
      setLatest(result)
      await load(true)
    } catch (e) {
      setError(e?.message || 'Prediction request failed.')
    } finally { setBusy(false) }
  }

  const prediction = latest?.forecast || []
  const lastActual = actual.length ? actual[actual.length - 1] : null
  const endDelta = latest?.end_prediction == null || lastActual == null ? null : latest.end_prediction - lastActual

  if (loading && !lab) return <div className="panel"><div className="panel-body">Loading prediction system…</div></div>

  return <>
    <div className="panel section-gap">
      <div className="panel-header"><span className="panel-title">Prediction Center</span><Badge tone={status?.telemetry_active ? 'healthy' : 'warning'}>{status?.telemetry_active ? 'Telemetry active' : 'Waiting for telemetry'}</Badge></div>
      <div className="panel-body"><p style={{color:'var(--text-dim)',fontSize:13,lineHeight:1.6,margin:0}}>Predictions are now durable records. New forecasts are created from new telemetry only, deduplicated by the exact input reading, and throttled so the ML service is not called repeatedly without new data.</p></div>
    </div>

    <div className="panel section-gap" style={{border:'1px solid var(--accent)'}}>
      <div className="panel-header"><span className="panel-title">Forecast configuration</span><Badge>Automatic + manual</Badge></div>
      <div className="panel-body">
        <div className="grid-2" style={{marginBottom:12}}>
          <label>Machine<select value={machineId} onChange={e=>{setMachineId(e.target.value);setLatest(null)}}>{machines.map(m => <option key={m.machine_id} value={m.machine_id}>{m.machine_name} · {m.category || 'other'}</option>)}</select></label>
          <label>Signal<select value={readingType} onChange={e=>{setReadingType(e.target.value);setLatest(null)}}><option value="temperature">Temperature</option><option value="vibration">Vibration</option><option value="current">Motor Current</option><option value="load">Machine Load</option><option value="humidity">Humidity</option></select></label>
          <label>Time-series model<select value={model} onChange={e=>{setModel(e.target.value);setLatest(null)}}><option value="chronos-bolt-tiny">Chronos-Bolt-Tiny</option><option value="timer">Timer</option></select></label>
          <label>Forecast horizon<select value={horizon} onChange={e=>setHorizon(Number(e.target.value))}><option value="6">6 steps</option><option value="12">12 steps</option><option value="24">24 steps</option></select></label>
        </div>
        <div className="chip-row">
          <button className="btn" onClick={runNow} disabled={busy || !machineId}>{busy ? 'Running model…' : 'Run now'}</button>
          <span style={{fontSize:11,color:'var(--text-faint)'}}><Clock3 size={12} style={{verticalAlign:'-2px'}}/> Automatic cadence: {Math.round((status?.interval_seconds || 300) / 60)} min after new telemetry</span>
          <span style={{fontSize:11,color:'var(--text-faint)'}}><Radio size={12} style={{verticalAlign:'-2px'}}/> {status?.telemetry_active ? 'New telemetry can trigger forecasting' : 'No recent telemetry: no automatic forecast calls'}</span>
        </div>
      </div>
    </div>

    {error && <div className="panel section-gap"><div className="panel-body" style={{color:'var(--critical)',fontSize:12}}>{error}</div></div>}

    <div className="stat-grid section-gap">
      <div className="stat-tile"><div className="stat-label"><BrainCircuit size={14}/> MODEL</div><div className="stat-value" style={{fontSize:18}}>{latest?.model || model}</div><div style={{fontSize:11,color:'var(--text-faint)'}}>{selectedMachine?.machine_name || 'Machine'}</div></div>
      <div className="stat-tile"><div className="stat-label"><Activity size={14}/> NEXT</div><div className="stat-value">{fmt(latest?.next_prediction)}</div><div style={{fontSize:11,color:'var(--text-faint)'}}>t+1 · {readingType}</div></div>
      <div className="stat-tile"><div className="stat-label"><TrendingUp size={14}/> END</div><div className="stat-value">{fmt(latest?.end_prediction)}</div><div style={{fontSize:11,color:'var(--text-faint)'}}>{latest?.trend || 'No forecast yet'}</div></div>
      <div className="stat-tile"><div className="stat-label"><Radio size={14}/> TELEMETRY</div><div className="stat-value" style={{fontSize:18}}>{status?.telemetry_active ? 'Active' : 'Idle'}</div><div style={{fontSize:11,color:'var(--text-faint)'}}>{status?.latest_telemetry_at ? formatDateTime(status.latest_telemetry_at) : 'No reading'}</div></div>
    </div>

    {latest?.available && <div className="panel section-gap"><div className="panel-header"><span className="panel-title">Latest saved prediction</span><Badge tone={latest.trigger === 'automatic' ? 'healthy' : 'neutral'}>{latest.trigger}</Badge></div><div className="panel-body"><SeriesChart actual={actual} forecast={prediction}/><div style={{display:'grid',gridTemplateColumns:'repeat(4,minmax(0,1fr))',gap:8,marginTop:12}}>{prediction.map((value,i)=><div key={i} style={{padding:9,borderRadius:7,background:'var(--panel-raised)',border:'1px solid var(--border)'}}><div className="mono" style={{fontWeight:700}}>{fmt(value)}</div><div style={{fontSize:10,color:'var(--text-faint)',marginTop:3}}>t+{i+1}</div></div>)}</div><div style={{marginTop:12,fontSize:12,color:'var(--text-dim)'}}>Current observed value: <b>{fmt(lastActual)}</b> · forecast endpoint delta: <b>{endDelta == null ? '—' : `${endDelta >= 0 ? '+' : ''}${fmt(endDelta)}`}</b>. This is a signal forecast, not a failure probability.</div></div></div>}

    <div className="panel section-gap"><div className="panel-header"><span className="panel-title"><History size={15} style={{verticalAlign:'-3px',marginRight:6}}/>Prediction history</span><span className="badge neutral">{history.length} saved</span></div><div className="panel-body"><table><thead><tr><th>Created</th><th>Trigger</th><th>Input end</th><th>Next</th><th>Endpoint</th><th>Trend</th><th>Status</th></tr></thead><tbody>{history.length ? history.map(run => <tr key={run.run_id}><td>{formatDateTime(run.created_at)}</td><td>{run.trigger}</td><td>{formatDateTime(run.input_ended_at)}</td><td className="mono">{fmt(run.next_prediction)}</td><td className="mono">{fmt(run.end_prediction)}</td><td>{run.trend === 'Increasing' ? <TrendingUp size={14}/> : run.trend === 'Decreasing' ? <TrendingDown size={14}/> : 'Stable'}</td><td><Badge tone="healthy">saved</Badge></td></tr>) : <tr><td colSpan="7" style={{textAlign:'center',padding:20,color:'var(--text-faint)'}}>No saved forecasts yet. Once enough telemetry arrives, automatic forecasting will create the first record.</td></tr>}</tbody></table></div></div>

    <div className="grid-2 section-gap"><div className="panel"><div className="panel-header"><span className="panel-title">Automatic forecasting</span><RefreshCw size={15}/></div><div className="panel-body" style={{fontSize:12,color:'var(--text-dim)',lineHeight:1.6}}><b>It does not run on a timer by itself.</b> The coordinator is invoked only after a new sensor reading commits. It then checks minimum history, telemetry freshness, cadence, and whether the exact input reading has already been forecast. If telemetry stops, no new prediction calls are made.</div></div><div className="panel"><div className="panel-header"><span className="panel-title">Model roles</span><Timer size={15}/></div><div className="panel-body" style={{fontSize:12,color:'var(--text-dim)',lineHeight:1.6}}><b>Chronos-Bolt-Tiny</b> is the default production forecast model for the constrained Render ML service. <b>Timer</b> is the secondary time-series model and can be selected for comparison when enabled. Neither model produces an uncalibrated failure probability.</div></div></div>
  </>
}
