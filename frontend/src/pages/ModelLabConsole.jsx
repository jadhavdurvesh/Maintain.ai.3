import { useEffect, useMemo, useRef, useState } from 'react'
import { Activity, BrainCircuit, Clock3, Gauge, History, RefreshCw, Target, TrendingUp } from 'lucide-react'
import api from '../api/client.js'
import { formatDateTime } from '../utils/dates.js'
import { usePageHeader } from '../PageHeaderContext.jsx'

const WINDOWS = ['24h', '48h', '7d', '30d']
const WINDOW_LABELS = { '24h': '24 hours', '48h': '48 hours', '7d': '7 days', '30d': '30 days' }
const WINDOW_STEPS = { '24h': '24 hourly steps', '48h': '48 hourly steps', '7d': '28 × 6-hour steps', '30d': '30 daily steps' }
const MIN = { 'chronos-bolt-tiny': 16, timer: 16 }
const fmt = (v, d = 2) => v == null || Number.isNaN(Number(v)) ? '—' : Number(v).toFixed(d)

function Badge({ children, tone = 'neutral' }) { return <span className={'badge ' + tone}>{children}</span> }

function ForecastChart({ actual = [], forecast = [] }) {
  const history = actual.slice(-32).map(Number).filter(Number.isFinite)
  const future = forecast.slice(0, 48).map(Number).filter(Number.isFinite)
  const all = [...history, ...future]
  if (!all.length) return <div className="empty-state">No telemetry or saved forecast is available for this selection yet.</div>
  const min = Math.min(...all), max = Math.max(...all), range = max - min || 1
  const width = 900, height = 270, count = history.length + future.length
  const point = (value, index) => `${(index / Math.max(count - 1, 1)) * width},${height - 24 - ((value - min) / range) * (height - 44)}`
  const actualPoints = history.map(point).join(' ')
  const forecastPoints = future.map((v, i) => point(v, history.length + i)).join(' ')
  const split = ((history.length - 1) / Math.max(count - 1, 1)) * width
  return <div style={{ background: 'var(--panel-raised)', border: '1px solid var(--border)', borderRadius: 12, padding: 12 }}>
    <svg viewBox={`0 0 ${width} ${height}`} width="100%" height="270" role="img" aria-label="Observed telemetry and saved forecast">
      {[58, 112, 166, 220].map(y => <line key={y} x1="0" y1={y} x2={width} y2={y} stroke="var(--border)" />)}
      {history.length > 0 && <line x1={split} y1="0" x2={split} y2={height} stroke="var(--text-faint)" strokeDasharray="5 5" />}
      {actualPoints && <polyline fill="none" stroke="var(--accent)" strokeWidth="3.5" strokeLinejoin="round" strokeLinecap="round" points={actualPoints} />}
      {forecastPoints && <polyline fill="none" stroke="var(--warning)" strokeWidth="3.5" strokeDasharray="8 6" strokeLinejoin="round" strokeLinecap="round" points={forecastPoints} />}
      <text x="8" y="18" fill="var(--text-faint)" fontSize="11">actual</text>
      {forecastPoints && <text x={Math.min(split + 8, width - 115)} y="18" fill="var(--warning)" fontSize="11">forecast</text>}
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

function HorizonCard({ name, run, selected, onSelect }) {
  const available = !!run?.available
  const running = run?.status === 'running' || !!run?.running
  return <button type="button" className="stat-tile" onClick={() => available && onSelect(name)} disabled={!available} style={{ minHeight: 138, textAlign: 'left', cursor: available ? 'pointer' : 'default', border: selected ? '1px solid var(--accent)' : '1px solid var(--border)', opacity: available ? 1 : .82 }}>
    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, alignItems: 'center' }}><div className="stat-label"><Clock3 size={13} /> {WINDOW_LABELS[name]}</div><Badge tone={available ? 'healthy' : running ? 'neutral' : 'warning'}>{available ? 'Forecasted' : running ? 'Running' : 'Waiting'}</Badge></div>
    {available ? <><div className="stat-value" style={{ fontSize: 21, marginTop: 10 }}>{fmt(run.end_prediction)}</div><div style={{ fontSize: 11, color: 'var(--text-faint)' }}>endpoint · {run.trend || 'Stable'} · {WINDOW_STEPS[name]}</div><div style={{ fontSize: 10, color: 'var(--text-faint)', marginTop: 7 }}>saved {formatDateTime(run.created_at)} · click to view</div></> : <><div style={{ fontSize: 12, color: 'var(--text-faint)', marginTop: 12, minHeight: 36 }}>{run?.reason || 'Waiting for automatic telemetry.'}</div><div style={{ fontSize: 10, color: 'var(--text-faint)', marginTop: 8 }}>Generated automatically from telemetry</div></>}
  </button>
}

function HistoryRow({ run, onOpen }) {
  const windowLabel = run.forecast_window ? WINDOW_LABELS[run.forecast_window] || run.forecast_window : `${run.horizon} steps`
  const usable = !!run.available
  return <button type="button" onClick={() => usable && onOpen(run)} disabled={!usable} style={{ width: '100%', textAlign: 'left', border: '1px solid var(--border)', background: 'var(--panel-raised)', borderRadius: 9, padding: '10px 12px', color: 'inherit', cursor: usable ? 'pointer' : 'default', opacity: usable ? 1 : .72 }}>
    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'center' }}>
      <div><div style={{ fontWeight: 700, fontSize: 12 }}>{windowLabel} · {run.model}</div><div style={{ fontSize: 10, color: 'var(--text-faint)', marginTop: 3 }}>{run.created_at ? formatDateTime(run.created_at) : '—'} · {run.trigger || 'automatic'}</div></div>
      <div style={{ textAlign: 'right' }}><div className="mono" style={{ fontWeight: 700 }}>{fmt(run.end_prediction)}</div><div style={{ fontSize: 10, color: 'var(--text-faint)' }}>{run.trend || run.status}</div></div>
    </div>
  </button>
}

export default function ModelLabConsole() {
  usePageHeader('AI Monitoring / Model Lab')
  const [lab, setLab] = useState(null)
  const [machineId, setMachineId] = useState('')
  const [signal, setSignal] = useState('temperature')
  const [model, setModel] = useState('chronos-bolt-tiny')
  const [horizon, setHorizon] = useState(12)
  const [status, setStatus] = useState(null)
  const [latest, setLatest] = useState(null)
  const [actual, setActual] = useState([])
  const [history, setHistory] = useState([])
  const [windows, setWindows] = useState(null)
  const [busy, setBusy] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [feedback, setFeedback] = useState(null)
  const [historyWindow, setHistoryWindow] = useState('short')
  const requestSeq = useRef(0)

  const machines = lab?.fleet?.machines || []
  const selected = useMemo(() => machines.find(m => String(m.machine_id) === String(machineId)), [machines, machineId])
  const samples = Number(status?.sample_count || 0)
  const minimum = Number(status?.minimum_samples || MIN[model] || 16)
  const canRun = !!machineId && samples >= minimum
  const selectedLabel = selected?.machine_name || 'Machine'
  const activeWindow = historyWindow !== 'short' ? historyWindow : null

  const load = async ({ preserve = true } = {}) => {
    const seq = ++requestSeq.current
    try {
      const data = await api.get('/api/analytics/model-lab')
      if (seq !== requestSeq.current) return
      setLab(data)
      const id = machineId || String(data?.fleet?.machines?.[0]?.machine_id || '')
      if (!id) { setLoading(false); return }
      if (!machineId) {
        setMachineId(id)
        return
      }

      // Always load the complete saved history. Filtering by the current short
      // horizon was the reason old predictions appeared to disappear when the
      // user changed steps or reopened the page.
      const [s, h, readings, w] = await Promise.all([
        api.get(`/api/predictions/machines/${id}/status?reading_type=${encodeURIComponent(signal)}&model=${encodeURIComponent(model)}&horizon=${horizon}`),
        api.get(`/api/predictions/machines/${id}/history?reading_type=${encodeURIComponent(signal)}&model=${encodeURIComponent(model)}&limit=100`),
        api.get(`/api/machines/${id}/readings?limit=64`),
        api.get(`/api/predictions/machines/${id}/windows?reading_type=${encodeURIComponent(signal)}&model=${encodeURIComponent(model)}`),
      ])
      if (seq !== requestSeq.current) return

      const runs = (h?.runs || []).filter(Boolean)
      const exactShort = runs.find(r => r.available && !r.forecast_window && Number(r.horizon) === Number(horizon))
      const fallbackShort = s?.latest_run?.available ? s.latest_run : null
      const selectedWindow = activeWindow ? w?.windows?.[activeWindow] : null
      const selectionKey = latest ? `${latest.machine_id}:${latest.reading_type}:${latest.model}` : ''
      const currentKey = `${id}:${signal}:${model}`

      setStatus(s)
      setHistory(runs)
      setWindows(w?.windows || null)
      setActual((readings || []).filter(r => r.reading_type === signal).sort((a, b) => new Date(a.recorded_at) - new Date(b.recorded_at)).map(r => Number(r.value)).filter(Number.isFinite).slice(-32))

      if (!preserve || selectionKey !== currentKey) {
        setLatest(selectedWindow?.available ? selectedWindow : exactShort || fallbackShort || null)
      } else if (activeWindow) {
        if (selectedWindow?.available) setLatest(selectedWindow)
      } else {
        // Do not clear an already visible chart just because a refresh races a
        // new telemetry write or the history endpoint temporarily returns empty.
        const currentRun = runs.find(r => r.available && r.run_id === latest?.run_id)
        if (!currentRun && exactShort) setLatest(exactShort)
        else if (!latest?.available && fallbackShort) setLatest(fallbackShort)
      }
      setError(null)
    } catch (e) {
      if (seq !== requestSeq.current) return
      setError(e?.message || 'Prediction center failed to load.')
    } finally {
      if (seq === requestSeq.current) setLoading(false)
    }
  }

  useEffect(() => {
    load({ preserve: false })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [machineId, signal, model, horizon, historyWindow])

  useEffect(() => {
    const t = window.setInterval(() => load({ preserve: true }), 30000)
    return () => window.clearInterval(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [machineId, signal, model, horizon, historyWindow])

  const run = async () => {
    if (!canRun || busy) return
    setBusy(true); setError(null); setFeedback(null)
    try {
      const result = await api.get(`/api/predictions/machines/${machineId}/forecast?reading_type=${encodeURIComponent(signal)}&model=${encodeURIComponent(model)}&horizon=${horizon}`)
      if (result?.available) setLatest(result)
      setFeedback(result?.available ? { tone: 'healthy', text: `Prediction saved · ${result.model} · ${horizon} steps · ${formatDateTime(result.created_at)}` } : { tone: 'warning', text: result?.reason || 'Prediction was not generated.' })
      await load({ preserve: true })
    } catch (e) {
      setError(e?.message || 'Prediction request failed.')
    } finally {
      setBusy(false)
    }
  }

  const openWindow = name => {
    const run = windows?.[name]
    if (!run?.available) return
    setHistoryWindow(name)
    setLatest(run)
    setFeedback({ tone: 'healthy', text: `${WINDOW_LABELS[name]} automatic forecast loaded from saved prediction.` })
  }

  const openHistory = run => {
    if (!run?.available) return
    setLatest(run)
    setHistoryWindow(run.forecast_window || 'short')
    if (!run.forecast_window && run.horizon) setHorizon(Number(run.horizon))
    setFeedback({ tone: 'healthy', text: 'Saved prediction loaded from history.' })
  }

  if (loading && !lab) return <div className="panel"><div className="panel-body">Loading prediction system…</div></div>

  const prediction = latest?.forecast || []
  const horizonRuns = windows || {}
  const recentHistory = history.filter(r => r.available).slice(0, 10)
  const latestLabel = activeWindow ? `${WINDOW_LABELS[activeWindow]} automatic forecast` : 'Latest saved prediction'

  return <>
    <div className="panel section-gap">
      <div className="panel-header"><span className="panel-title">Prediction Center</span><div style={{ display: 'flex', gap: 8, alignItems: 'center' }}><Badge tone={status?.telemetry_active ? 'healthy' : 'warning'}>{status?.telemetry_active ? 'Telemetry active' : 'Telemetry stale · saved replay available'}</Badge><span className="badge neutral">{samples} samples</span></div></div>
      <div className="panel-body" style={{ paddingTop: 8, paddingBottom: 10, color: 'var(--text-dim)', fontSize: 12 }}>Historical telemetry → selected forecasting model → future signal trajectory. Saved predictions are restored for the same machine, signal, model and horizon.</div>
    </div>

    <div className="panel section-gap" style={{ border: '1px solid var(--accent)', boxShadow: '0 0 28px rgba(0,200,255,.07)' }}>
      <div className="panel-header"><span className="panel-title">Forecast configuration</span><Badge>{model === 'timer' ? 'Timer-Lite · CPU-safe' : 'Chronos-Bolt-Tiny · production'}</Badge></div>
      <div className="panel-body">
        <div className="grid-2" style={{ marginBottom: 12 }}>
          <label>Machine<select value={machineId} onChange={e => { setMachineId(e.target.value); setLatest(null); setHistoryWindow('short'); setFeedback(null) }}>{machines.map(m => <option key={m.machine_id} value={m.machine_id}>{m.machine_name} · {m.category || 'other'}</option>)}</select></label>
          <label>Signal<select value={signal} onChange={e => { setSignal(e.target.value); setLatest(null); setHistoryWindow('short'); setFeedback(null) }}><option value="temperature">Temperature</option><option value="vibration">Vibration</option><option value="current">Current</option><option value="load">Load</option><option value="humidity">Humidity</option></select></label>
        </div>
        <div className="grid-2">
          <label>Forecast model<select value={model} onChange={e => { setModel(e.target.value); setLatest(null); setHistoryWindow('short'); setFeedback(null) }}><option value="chronos-bolt-tiny">Chronos-Bolt-Tiny</option><option value="timer">Timer-Lite</option></select></label>
          <label>Prediction horizon<select value={horizon} onChange={e => { setHorizon(Number(e.target.value)); setHistoryWindow('short') }}>{[6, 12, 24, 48].map(v => <option key={v} value={v}>{v} steps</option>)}</select></label>
        </div>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center', marginTop: 14, flexWrap: 'wrap' }}>
          <button className="primary-button" type="button" disabled={!canRun || busy} onClick={run}><BrainCircuit size={15} /> {busy ? 'Running…' : 'Run prediction'}</button>
          <span style={{ fontSize: 11, color: 'var(--text-faint)' }}>5 min automatic cadence · {samples}/{minimum} samples ready</span>
          {error && <span style={{ color: 'var(--danger)', fontSize: 11 }}>{error}</span>}
        </div>
        {feedback && <div style={{ marginTop: 12, padding: '9px 12px', border: '1px solid var(--border)', borderRadius: 9, color: feedback.tone === 'healthy' ? 'var(--text)' : 'var(--warning)', background: 'var(--panel-raised)', fontSize: 12 }}>{feedback.text}</div>}
      </div>
    </div>

    <div className="panel section-gap">
      <div className="panel-header"><span className="panel-title">{latestLabel}</span><div style={{ display: 'flex', gap: 8, alignItems: 'center' }}><Badge tone="healthy">{latest?.available ? 'Saved' : 'No saved forecast'}</Badge><button className="icon-button" type="button" title="Refresh" onClick={() => load({ preserve: true })}><RefreshCw size={15} /></button></div></div>
      <div className="panel-body">
        {latest?.available ? <>
          <Summary forecast={latest} actual={actual} />
          <ForecastChart actual={actual} forecast={prediction} />
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,minmax(0,1fr))', gap: 8, marginTop: 10 }}>
            {prediction.slice(0, 12).map((value, index) => <div key={index} className="stat-tile" style={{ padding: 10 }}><div className="mono" style={{ fontWeight: 700 }}>{fmt(value)}</div><div style={{ fontSize: 10, color: 'var(--text-faint)' }}>t+{index + 1}</div></div>)}
          </div>
          <div style={{ marginTop: 12, fontSize: 11, color: 'var(--text-faint)' }}><b>How to read this:</b> solid = observed machine signal; dashed = selected model forecast. This is a signal forecast, not a failure probability.</div>
        </> : <div className="empty-state">No saved forecast for {selectedLabel} / {signal} / {model} / {horizon} steps yet. Run the short forecast once; automatic forecasts will then persist as telemetry arrives.</div>}
      </div>
    </div>

    <div className="panel section-gap">
      <div className="panel-header"><span className="panel-title">Machine forecast horizons · {selectedLabel}</span><Badge>Automatic · saved per machine</Badge></div>
      <div className="panel-body">
        <div className="stat-grid">
          {WINDOWS.map(name => <HorizonCard key={name} name={name} run={horizonRuns[name]} selected={activeWindow === name} onSelect={openWindow} />)}
        </div>
        <div style={{ marginTop: 10, fontSize: 11, color: 'var(--text-faint)' }}>24h = 24 hourly steps · 48h = 48 hourly steps · 7d = 28 six-hour steps · 30d = 30 daily steps. These are generated automatically from fresh telemetry; no manual horizon execution is required.</div>
      </div>
    </div>

    <div className="panel section-gap">
      <div className="panel-header"><span className="panel-title"><History size={15} /> Saved prediction history</span><Badge>{recentHistory.length} records</Badge></div>
      <div className="panel-body">
        {recentHistory.length ? <div style={{ display: 'grid', gap: 8 }}>{recentHistory.map(run => <HistoryRow key={run.run_id} run={run} onOpen={openHistory} />)}</div> : <div className="empty-state">No saved predictions for this machine, signal and model yet.</div>}
      </div>
    </div>

    <div className="panel section-gap">
      <div className="panel-header"><span className="panel-title">Forecast notes</span><Badge>Production model output</Badge></div>
      <div className="panel-body" style={{ fontSize: 12, color: 'var(--text-dim)', lineHeight: 1.6 }}>Forecasts are durable records tied to machine telemetry. Automatic inference waits for fresh, deduplicated sensor data and the model minimum history. Timer uses the lightweight Timer-Lite path to avoid loading the heavy checkpoint.</div>
    </div>
  </>
}
