import { useEffect, useMemo, useState } from 'react'
import { Activity, BrainCircuit, CheckCircle2, Clock3, Gauge, History, Radio, RefreshCw, Target, Timer, TrendingDown, TrendingUp, Zap } from 'lucide-react'
import api from '../api/client.js'
import { formatDateTime } from '../utils/dates.js'
import { usePageHeader } from '../PageHeaderContext.jsx'

const WINDOWS = ['24h', '48h', '7d', '30d']
const LABELS = { '24h': '24 hours', '48h': '48 hours', '7d': '7 days', '30d': '30 days' }
const STEPS = { '24h': '24 hourly steps', '48h': '48 hourly steps', '7d': '28 × 6-hour steps', '30d': '30 daily steps' }
const MIN = { 'chronos-bolt-tiny': 16, timer: 16 }
const fmt = (v, d = 2) => v == null || Number.isNaN(Number(v)) ? '—' : Number(v).toFixed(d)

function Badge({ children, tone = 'neutral' }) { return <span className={'badge ' + tone}>{children}</span> }

function ForecastChart({ actual = [], forecast = [] }) {
  const history = actual.slice(-32).map(Number).filter(Number.isFinite)
  const future = forecast.slice(0, 48).map(Number).filter(Number.isFinite)
  const all = [...history, ...future]
  if (!all.length) return <div className="empty-state">No telemetry or forecast values available yet.</div>
  const min = Math.min(...all), max = Math.max(...all), range = max - min || 1
  const width = 900, height = 260
  const point = (v, i, count) => `${(i / Math.max(count - 1, 1)) * width},${height - 20 - ((v - min) / range) * (height - 40)}`
  const count = history.length + future.length
  const actualPoints = history.map((v, i) => point(v, i, count)).join(' ')
  const forecastPoints = future.map((v, i) => point(v, history.length + i, count)).join(' ')
  const split = ((history.length - 1) / Math.max(count - 1, 1)) * width
  return <div style={{ overflowX: 'auto', background: 'var(--panel-raised)', border: '1px solid var(--border)', borderRadius: 10, padding: 10 }}>
    <svg viewBox={`0 0 ${width} ${height}`} width="100%" height="260" role="img" aria-label="Historical telemetry and forecast">
      {[55, 110, 165, 220].map(y => <line key={y} x1="0" y1={y} x2={width} y2={y} stroke="var(--border)" />)}
      <line x1={split} y1="0" x2={split} y2={height} stroke="var(--text-faint)" strokeDasharray="5 5" />
      {actualPoints && <polyline fill="none" stroke="var(--accent)" strokeWidth="3" points={actualPoints} />}
      {forecastPoints && <polyline fill="none" stroke="var(--warning)" strokeWidth="3" strokeDasharray="7 5" points={forecastPoints} />}
      <text x="8" y="18" fill="var(--text-faint)" fontSize="11">actual</text>
      <text x={Math.min(split + 8, width - 120)} y="18" fill="var(--warning)" fontSize="11">forecast</text>
    </svg>
    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'var(--text-faint)' }}><span>Older telemetry</span><span>Now → predicted future</span></div>
  </div>
}

function Summary({ forecast, actual }) {
  const values = (forecast?.forecast || []).map(Number).filter(Number.isFinite)
  if (!values.length) return null
  const baseline = actual.length ? Number(actual[actual.length - 1]) : null
  const first = values[0], last = values[values.length - 1]
  const delta = baseline == null ? null : first - baseline
  const total = baseline == null ? null : last - baseline
  const trend = total == null || Math.abs(total) < 1e-6 ? 'Stable' : total > 0 ? 'Increasing' : 'Decreasing'
  return <div className="stat-grid section-gap">
    <div className="stat-tile"><div className="stat-label"><Target size={14} /> NEXT PREDICTION</div><div className="stat-value" style={{ fontSize: 22 }}>{fmt(first)}</div><div style={{ fontSize: 11, color: 'var(--text-faint)' }}>t+1</div></div>
    <div className="stat-tile"><div className="stat-label"><TrendingUp size={14} /> END OF HORIZON</div><div className="stat-value" style={{ fontSize: 22 }}>{fmt(last)}</div><div style={{ fontSize: 11, color: 'var(--text-faint)' }}>t+{values.length}</div></div>
    <div className="stat-tile"><div className="stat-label"><Gauge size={14} /> EXPECTED TREND</div><div className="stat-value" style={{ fontSize: 22 }}>{trend}</div><div style={{ fontSize: 11, color: 'var(--text-faint)' }}>{total == null ? 'No baseline' : `${total >= 0 ? '+' : ''}${fmt(total)} vs latest`}</div></div>
    <div className="stat-tile"><div className="stat-label"><Activity size={14} /> MODEL OUTPUT</div><div className="stat-value" style={{ fontSize: 22 }}>{fmt(delta)}</div><div style={{ fontSize: 11, color: 'var(--text-faint)' }}>first step vs latest</div></div>
  </div>
}

function HorizonCard({ name, run, busy, canRun, onRun }) {
  const available = !!run?.available
  return <div className="stat-tile" style={{ minHeight: 155 }}>
    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, alignItems: 'center' }}><div className="stat-label"><Clock3 size={13} /> {LABELS[name]}</div><Badge tone={available ? 'healthy' : 'warning'}>{available ? 'Forecasted' : 'Waiting'}</Badge></div>
    {available ? <><div className="stat-value" style={{ fontSize: 20, marginTop: 8 }}>{fmt(run.end_prediction)}</div><div style={{ fontSize: 11, color: 'var(--text-faint)' }}>endpoint · {run.trend || '—'} · {STEPS[name]}</div><div style={{ fontSize: 10, color: 'var(--text-faint)', marginTop: 5 }}>saved {formatDateTime(run.created_at)}</div></> : <div style={{ fontSize: 12, color: 'var(--text-faint)', marginTop: 12, minHeight: 34 }}>{run?.reason || 'Waiting for enough telemetry.'}</div>}
    <button className="btn secondary" style={{ marginTop: 10, padding: '5px 9px' }} disabled={busy || !canRun} onClick={() => onRun(name)}>{busy ? <><RefreshCw size={12} /> Running…</> : <><Zap size={12} /> Run {name}</>}</button>
  </div>
}

export default function ModelLabConsole() {
  usePageHeader('AI Monitoring / Model Lab')
  const [lab, setLab] = useState(null), [machineId, setMachineId] = useState(''), [signal, setSignal] = useState('temperature'), [model, setModel] = useState('chronos-bolt-tiny'), [horizon, setHorizon] = useState(12)
  const [status, setStatus] = useState(null), [latest, setLatest] = useState(null), [actual, setActual] = useState([]), [history, setHistory] = useState([]), [windows, setWindows] = useState(null), [fleet, setFleet] = useState(null)
  const [busy, setBusy] = useState(false), [windowBusy, setWindowBusy] = useState(''), [loading, setLoading] = useState(true), [error, setError] = useState(null), [feedback, setFeedback] = useState(null), [historyWindow, setHistoryWindow] = useState('short')
  const machines = lab?.fleet?.machines || []
  const selected = useMemo(() => machines.find(m => String(m.machine_id) === String(machineId)), [machines, machineId])
  const samples = Number(status?.sample_count || 0)
  const minimum = MIN[model] || 16
  const canRun = !!machineId && samples >= minimum

  const load = async (preserve = true) => {
    try {
      const data = await api.get('/api/analytics/model-lab')
      setLab(data)
      const id = machineId || String(data?.fleet?.machines?.[0]?.machine_id || '')
      if (!machineId && id) setMachineId(id)
      if (!id) return
      const hq = historyWindow === 'short'
        ? `/api/predictions/machines/${id}/history?reading_type=${encodeURIComponent(signal)}&model=${encodeURIComponent(model)}&horizon=${horizon}&limit=50`
        : `/api/predictions/machines/${id}/history?reading_type=${encodeURIComponent(signal)}&model=${encodeURIComponent(model)}&forecast_window=${historyWindow}&limit=50`
      const [s, h, r, w, f] = await Promise.all([
        api.get(`/api/predictions/machines/${id}/status?reading_type=${encodeURIComponent(signal)}&model=${encodeURIComponent(model)}&horizon=${horizon}`),
        api.get(hq),
        api.get(`/api/machines/${id}/readings?limit=64`),
        api.get(`/api/predictions/machines/${id}/windows?reading_type=${encodeURIComponent(signal)}&model=${encodeURIComponent(model)}`),
        api.get(`/api/predictions/fleet/windows?reading_type=${encodeURIComponent(signal)}&model=${encodeURIComponent(model)}`),
      ])
      setStatus(s); setHistory(h?.runs || []); setWindows(w?.windows || null); setFleet(f || null)
      setActual((r || []).filter(x => x.reading_type === signal).sort((a, b) => new Date(a.recorded_at) - new Date(b.recorded_at)).map(x => Number(x.value)).filter(Number.isFinite).slice(-32))
      if (!preserve || !latest) setLatest(h?.runs?.[0] || null)
      setError(null)
    } catch (e) { setError(e?.message || 'Prediction center failed to load.') }
    finally { setLoading(false) }
  }

  useEffect(() => { load(false) }, [machineId, signal, model, horizon, historyWindow])
  useEffect(() => { const t = window.setInterval(() => load(true), 30000); return () => window.clearInterval(t) }, [machineId, signal, model, horizon, historyWindow])

  const run = async () => {
    if (!canRun) return
    setBusy(true); setError(null); setFeedback(null)
    try {
      const result = await api.get(`/api/predictions/machines/${machineId}/forecast?reading_type=${encodeURIComponent(signal)}&model=${encodeURIComponent(model)}&horizon=${horizon}`)
      setLatest(result)
      setFeedback(result?.available ? { tone: 'healthy', text: `Prediction saved · ${result.model} · ${horizon} steps · ${formatDateTime(result.created_at)}` } : { tone: 'warning', text: result?.reason || 'Prediction was not generated.' })
      await load(true)
    } catch (e) { setError(e?.message || 'Prediction request failed.') }
    finally { setBusy(false) }
  }

  const runWindow = async name => {
    if (!canRun) return
    setWindowBusy(name); setError(null); setFeedback(null)
    try {
      const result = await api.get(`/api/predictions/machines/${machineId}/windows/run?window=${name}&reading_type=${encodeURIComponent(signal)}&model=${encodeURIComponent(model)}`)
      const saved = result?.run || result
      setLatest(saved)
      setFeedback(saved?.available ? { tone: 'healthy', text: `${LABELS[name]} forecast saved · ${saved.horizon} steps` } : { tone: 'warning', text: saved?.reason || result?.reason || 'Forecast was not generated.' })
      setHistoryWindow(name)
      await load(true)
    } catch (e) { setError(e?.message || `${name} forecast failed.`) }
    finally { setWindowBusy('') }
  }

  if (loading && !lab) return <div className="panel"><div className="panel-body">Loading prediction system…</div></div>
  const prediction = latest?.forecast || []

  return <>
    <div className="panel section-gap"><div className="panel-header"><span className="panel-title">Prediction Center</span><div style={{ display: 'flex', gap: 8, alignItems: 'center' }}><Badge tone={status?.telemetry_active ? 'healthy' : 'warning'}>{status?.telemetry_active ? 'Telemetry active' : 'Telemetry stale · manual replay available'}</Badge><span className="badge neutral">{samples} samples</span></div></div><div className="panel-body" style={{ paddingTop: 8, paddingBottom: 10, color: 'var(--text-dim)', fontSize: 12 }}>Historical telemetry → selected forecasting model → future signal trajectory. Forecast values are not failure probabilities.</div></div>

    <div className="panel section-gap" style={{ border: '1px solid var(--accent)' }}><div className="panel-header"><span className="panel-title">Forecast configuration</span><Badge>{model === 'timer' ? 'Timer-Lite · CPU-safe' : 'Chronos-Bolt-Tiny · production'}</Badge></div><div className="panel-body">
      <div className="grid-2" style={{ marginBottom: 12 }}>
        <label>Machine<select value={machineId} onChange={e => { setMachineId(e.target.value); setLatest(null) }}>{machines.map(m => <option key={m.machine_id} value={m.machine_id}>{m.machine_name} · {m.category || 'other'}</option>)}</select></label>
        <label>Signal<select value={signal} onChange={e => { setSignal(e.target.value); setLatest(null) }}><option value="temperature">Temperature</option><option value="vibration">Vibration</option><option value="current">Motor Current</option><option value="load">Machine Load</option><option value="humidity">Humidity</option></select></label>
        <label>Forecast model<select value={model} onChange={e => { setModel(e.target.value); setLatest(null) }}><option value="chronos-bolt-tiny">Chronos-Bolt-Tiny</option><option value="timer">Timer-Lite</option></select></label>
        <label>Prediction horizon<select value={horizon} onChange={e => setHorizon(Number(e.target.value))}><option value="6">6 steps</option><option value="12">12 steps</option><option value="24">24 steps</option></select></label>
      </div>
      <div className="chip-row" style={{ alignItems: 'center' }}><button className="btn" onClick={run} disabled={busy || !canRun}>{busy ? <><RefreshCw size={14} /> Running model…</> : <><BrainCircuit size={14} /> Run prediction</>}</button><span style={{ fontSize: 11, color: 'var(--text-faint)' }}><Clock3 size={12} style={{ verticalAlign: '-2px' }} /> {Math.round((status?.interval_seconds || 300) / 60)} min automatic cadence</span><span style={{ fontSize: 11, color: canRun ? 'var(--text-faint)' : 'var(--warning)' }}><Radio size={12} style={{ verticalAlign: '-2px' }} /> {canRun ? `${samples}/${minimum} samples ready` : `Need ${minimum} samples · currently ${samples}`}</span></div>
      {feedback && <div style={{ marginTop: 12, padding: '10px 12px', borderRadius: 8, border: '1px solid var(--border)', background: 'var(--panel-raised)', fontSize: 12, display: 'flex', alignItems: 'center', gap: 8 }}><CheckCircle2 size={15} /><span>{feedback.text}</span></div>}
    </div></div>

    {error && <div className="panel section-gap"><div className="panel-body" style={{ color: 'var(--critical)', fontSize: 12 }}>{error}</div></div>}

    {latest?.available && <><Summary forecast={latest} actual={actual} /><div className="panel section-gap"><div className="panel-header"><span className="panel-title">Forecast chart</span><Badge tone="healthy">Saved · {latest.model}</Badge></div><div className="panel-body"><ForecastChart actual={actual} forecast={prediction}/><div style={{ marginTop: 12, display: 'grid', gridTemplateColumns: 'repeat(4,minmax(0,1fr))', gap: 8 }}>{prediction.slice(0, horizon).map((v, i) => <div key={i} style={{ padding: 9, borderRadius: 7, background: 'var(--panel-raised)', border: '1px solid var(--border)' }}><div className="mono" style={{ fontWeight: 700 }}>{fmt(v)}</div><div style={{ fontSize: 10, color: 'var(--text-faint)', marginTop: 3 }}>t+{i + 1}</div></div>)}</div><div style={{ marginTop: 12, fontSize: 12, color: 'var(--text-dim)' }}><b>How to read this:</b> solid = observed machine signal; dashed = selected model forecast. A rising or falling trajectory is signal evidence and should be interpreted with degradation evidence, limits, maintenance history and technician inspection.</div></div></div></>}

    <div className="panel section-gap"><div className="panel-header"><span className="panel-title">Machine forecast horizons · {selected?.machine_name || 'Machine'}</span><Badge>Saved per machine</Badge></div><div className="panel-body"><div className="stat-grid">{WINDOWS.map(name => <HorizonCard key={name} name={name} run={windows?.[name]} busy={windowBusy === name} canRun={canRun} onRun={runWindow}/>)}</div><div style={{ marginTop: 12, fontSize: 11, color: 'var(--text-faint)' }}>24h = 24 hourly steps · 48h = 48 hourly steps · 7d = 28 six-hour steps · 30d = 30 daily steps. Manual runs use stored telemetry when live telemetry is stale.</div></div></div>

    <div className="panel section-gap"><div className="panel-header"><span className="panel-title">Fleet forecast matrix</span><span className="badge neutral">{fleet?.machines?.length || 0} machines</span></div><div className="panel-body"><div style={{ overflowX: 'auto' }}><table><thead><tr><th>Machine</th><th>Telemetry</th><th>24h</th><th>48h</th><th>7d</th><th>30d</th></tr></thead><tbody>{(fleet?.machines || []).map(m => <tr key={m.machine_id}><td><button className="btn secondary" style={{ padding: '4px 8px' }} onClick={() => { setMachineId(String(m.machine_id)); setLatest(null) }}>{m.machine_name}</button></td><td>{m.telemetry_at ? formatDateTime(m.telemetry_at) : <Badge tone="warning">No telemetry</Badge>}</td>{WINDOWS.map(w => { const r = m.windows?.[w]; return <td key={w}>{r?.available ? <><b className="mono">{fmt(r.end_prediction)}</b><div style={{ fontSize: 10, color: 'var(--text-faint)' }}>{r.trend || '—'}</div></> : <span style={{ fontSize: 10, color: 'var(--text-faint)' }}>waiting</span>}</td> })}</tr>)}{!(fleet?.machines || []).length && <tr><td colSpan="6" style={{ textAlign: 'center', padding: 20, color: 'var(--text-faint)' }}>No fleet forecast data yet.</td></tr>}</tbody></table></div></div></div>

    <div className="panel section-gap"><div className="panel-header"><span className="panel-title"><History size={15} style={{ verticalAlign: '-3px', marginRight: 6 }} />Prediction history</span><div style={{ display: 'flex', gap: 8, alignItems: 'center' }}><select value={historyWindow} onChange={e => setHistoryWindow(e.target.value)}><option value="short">Short · {horizon} steps</option>{WINDOWS.map(w => <option key={w} value={w}>{LABELS[w]}</option>)}</select><span className="badge neutral">{history.length} saved</span></div></div><div className="panel-body"><div style={{ overflowX: 'auto' }}><table><thead><tr><th>Created</th><th>Trigger</th><th>Steps</th><th>Next</th><th>Endpoint</th><th>Trend</th></tr></thead><tbody>{history.length ? history.map(r => <tr key={r.run_id}><td>{formatDateTime(r.created_at)}</td><td>{r.trigger}</td><td>{r.horizon}</td><td className="mono">{fmt(r.next_prediction)}</td><td className="mono">{fmt(r.end_prediction)}</td><td>{r.trend === 'Increasing' ? <TrendingUp size={14}/> : r.trend === 'Decreasing' ? <TrendingDown size={14}/> : 'Stable'}</td></tr>) : <tr><td colSpan="6" style={{ textAlign: 'center', padding: 20, color: 'var(--text-faint)' }}>No saved forecasts for this selection yet.</td></tr>}</tbody></table></div></div></div>

    <div className="grid-2 section-gap"><div className="panel"><div className="panel-header"><span className="panel-title">Automatic forecasting</span><RefreshCw size={15}/></div><div className="panel-body" style={{ fontSize: 12, color: 'var(--text-dim)', lineHeight: 1.6 }}><b>Telemetry-driven, not a blind timer.</b> Fresh readings can trigger inference after freshness, history, cadence and duplicate checks. When telemetry stops, automatic inference pauses; manual replay remains available.</div></div><div className="panel"><div className="panel-header"><span className="panel-title">Model roles</span><Timer size={15}/></div><div className="panel-body" style={{ fontSize: 12, color: 'var(--text-dim)', lineHeight: 1.6 }}><b>Chronos-Bolt-Tiny</b> is the default production path. <b>Timer-Lite</b> is the memory-safe secondary CPU path on the ML service. It preserves the forecast contract without loading the heavy Timer checkpoint.</div></div></div>
  </>
}
