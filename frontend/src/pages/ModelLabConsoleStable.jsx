import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Activity, BrainCircuit, CheckCircle2, Clock3, Gauge, History, Loader2, Play, Plus, RefreshCw, Target, TrendingDown, TrendingUp, Zap } from 'lucide-react'
import api from '../api/client.js'
import { formatDateTime } from '../utils/dates.js'
import { usePageHeader } from '../PageHeaderContext.jsx'
import './ModelLabConsoleStable.css'
import { clearPredictionTask, getPredictionTask, startPredictionTask, subscribePredictionTasks } from '../api/predictionTask.js'

const WINDOWS = ['24h', '48h', '7d', '30d']
const WINDOW_LABELS = { '24h': '24 hours', '48h': '48 hours', '7d': '7 days', '30d': '30 days' }
const WINDOW_STEPS = { '24h': '24 hourly points', '48h': '48 hourly points', '7d': '28 six-hour points', '30d': '30 daily points' }
const MIN = { 'chronos-bolt-tiny': 16, timer: 16 }
const fmt = (v, d = 2) => v == null || !Number.isFinite(Number(v)) ? '—' : Number(v).toFixed(d)

function Pill({ children, tone = 'neutral' }) { return <span className={`badge ${tone}`}>{children}</span> }

function Field({ label, value, onChange, children, hint }) {
  return <label className="ml-field">
    <span>{label}</span>
    <select value={value} onChange={e => onChange(e.target.value)}>{children}</select>
    {hint && <small>{hint}</small>}
  </label>
}

function ForecastChart({ actual, forecast }) {
  const history = actual.map(Number).filter(Number.isFinite).slice(-32)
  const future = forecast.map(Number).filter(Number.isFinite).slice(0, 48)
  const all = [...history, ...future]
  if (!all.length) return <div className="ml-chart-empty">No telemetry or saved forecast is available for this selection.</div>

  const width = 1000
  const height = 340
  const min = Math.min(...all)
  const max = Math.max(...all)
  const range = max - min || 1
  const count = Math.max(history.length + future.length, 2)
  const x = index => (index / (count - 1)) * width
  const y = value => height - 42 - ((value - min) / range) * (height - 84)
  const actualPoints = history.map((v, i) => `${x(i)},${y(v)}`).join(' ')
  const forecastPoints = future.map((v, i) => `${x(history.length + i)},${y(v)}`).join(' ')
  const split = history.length > 1 ? x(history.length - 1) : 0

  return <div className="ml-chart">
    <div className="ml-chart-head">
      <div className="ml-legend"><span><i className="observed" />Observed telemetry</span><span><i className="forecast" />Model forecast</span></div>
      <span>history → forecast</span>
    </div>
    <svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" role="img" aria-label="Observed telemetry and forecast">
      {[58, 122, 186, 250, 314].map(yPos => <line key={yPos} x1="0" y1={yPos} x2={width} y2={yPos} stroke="var(--border)" />)}
      {history.length > 1 && <line x1={split} y1="0" x2={split} y2={height} stroke="var(--text-faint)" strokeDasharray="6 7" />}
      {actualPoints && <polyline points={actualPoints} fill="none" stroke="var(--accent)" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" />}
      {forecastPoints && <polyline points={forecastPoints} fill="none" stroke="var(--warning)" strokeWidth="4" strokeDasharray="10 7" strokeLinecap="round" strokeLinejoin="round" />}
      <text x="12" y="22" fill="var(--text-faint)" fontSize="11">ACTUAL</text>
      {forecastPoints && <text x={Math.min(split + 12, width - 110)} y="22" fill="var(--warning)" fontSize="11">FORECAST</text>}
    </svg>
    <div className="ml-chart-foot"><span>Older telemetry</span><span>Now → predicted future</span></div>
  </div>
}

function Stat({ icon: Icon, label, value, sub }) {
  return <div className="ml-stat"><div className="ml-stat-label"><Icon size={14} />{label}</div><strong>{value}</strong><small>{sub}</small></div>
}

function HorizonCard({ name, run, selected, onOpen }) {
  const available = !!run?.available
  return <button type="button" className={`ml-horizon ${selected ? 'selected' : ''} ${available ? 'available' : ''}`} disabled={!available} onClick={() => available && onOpen(name)}>
    <div className="ml-horizon-top"><span><Clock3 size={13} />{WINDOW_LABELS[name]}</span><Pill tone={available ? 'healthy' : 'warning'}>{available ? 'Ready' : 'Waiting'}</Pill></div>
    {available ? <><strong>{fmt(run.end_prediction)}</strong><small>endpoint · {run.trend || 'Stable'} · {WINDOW_STEPS[name]}</small><em>Saved {formatDateTime(run.created_at)}</em></> : <><p>{run?.reason || 'Generated automatically when telemetry is available.'}</p><em>Automatic · no manual run</em></>}
  </button>
}

function HistoryItem({ run, onOpen }) {
  const label = run.forecast_window ? WINDOW_LABELS[run.forecast_window] || run.forecast_window : `${run.horizon || '—'} steps`
  return <button type="button" className="ml-history-item" onClick={() => onOpen(run)}>
    <div><strong>{label} · {run.model || 'model'}</strong><small>{run.created_at ? formatDateTime(run.created_at) : '—'} · {run.trigger || 'automatic'}</small></div>
    <div className="ml-history-value"><strong>{fmt(run.end_prediction)}</strong><small>{run.trend || run.status || 'saved'}</small></div>
  </button>
}

export default function ModelLabConsoleStable() {
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
  const [activeWindow, setActiveWindow] = useState('short')
  const [busy, setBusy] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [feedback, setFeedback] = useState(null)
  const [taskVersion, setTaskVersion] = useState(0)
  const requestSeq = useRef(0)

  const machines = lab?.fleet?.machines || []
  const selected = useMemo(() => machines.find(m => String(m.machine_id) === String(machineId)), [machines, machineId])
  const selectedLabel = selected?.machine_name || 'Machine'
  const samples = Number(status?.sample_count || 0)
  const minimum = Number(status?.minimum_samples || MIN[model] || 16)
  const canRun = !!machineId && samples >= minimum
  const forecast = latest?.forecast || []
  const baseline = actual.length ? Number(actual[actual.length - 1]) : null
  const first = forecast.length ? Number(forecast[0]) : null
  const last = forecast.length ? Number(forecast[forecast.length - 1]) : null
  const total = baseline != null && last != null ? last - baseline : null
  const trend = total == null || Math.abs(total) < 1e-6 ? 'Stable' : total > 0 ? 'Increasing' : 'Decreasing'
  const recentHistory = history.filter(r => r.available).slice(0, 12)
  const taskKey = machineId ? `${machineId}::${signal}::${model}::${horizon}` : null
  const predictionTask = taskKey ? getPredictionTask(taskKey) : null
  const taskBusy = predictionTask?.status === 'running'

  const load = useCallback(async ({ restore = false } = {}) => {
    const seq = ++requestSeq.current
    try {
      const data = await api.get('/api/analytics/model-lab')
      if (seq !== requestSeq.current) return
      setLab(data)
      const id = machineId || String(data?.fleet?.machines?.[0]?.machine_id || '')
      if (!id) return
      if (!machineId) { setMachineId(id); return }

      const [s, h, readings, w] = await Promise.all([
        api.get(`/api/predictions/machines/${id}/status?reading_type=${encodeURIComponent(signal)}&model=${encodeURIComponent(model)}&horizon=${horizon}`),
        api.get(`/api/predictions/machines/${id}/history?reading_type=${encodeURIComponent(signal)}&model=${encodeURIComponent(model)}&limit=100`),
        api.get(`/api/machines/${id}/readings?limit=64`),
        api.get(`/api/predictions/machines/${id}/windows?reading_type=${encodeURIComponent(signal)}&model=${encodeURIComponent(model)}`),
      ])
      if (seq !== requestSeq.current) return

      const runs = Array.isArray(h?.runs) ? h.runs.filter(r => r?.available) : []
      const exact = runs.find(r => !r.forecast_window && Number(r.horizon) === Number(horizon))
      const selectedSaved = activeWindow !== 'short' ? w?.windows?.[activeWindow] : null
      setStatus(s)
      setHistory(runs)
      setWindows(w?.windows || null)
      setActual((readings || []).filter(r => r.reading_type === signal).sort((a, b) => new Date(a.recorded_at) - new Date(b.recorded_at)).map(r => Number(r.value)).filter(Number.isFinite).slice(-32))

      // Only replace the displayed forecast when explicitly restoring a machine/selection.
      // Background refreshes never clear the chart. This prevents the chart from flashing
      // away when telemetry/history requests briefly return an empty or stale response.
      if (restore) {
        setLatest(selectedSaved?.available ? selectedSaved : exact || (s?.latest_run?.available ? s.latest_run : null))
      }
      setError(null)
    } catch (e) {
      if (seq === requestSeq.current) setError(e?.message || 'Prediction center failed to load.')
    } finally {
      if (seq === requestSeq.current) setLoading(false)
    }
  }, [machineId, signal, model, horizon, activeWindow])

  useEffect(() => subscribePredictionTasks(() => setTaskVersion(v => v + 1)), [])
  useEffect(() => {
    if (!taskKey) return
    const task = getPredictionTask(taskKey)
    if (!task) return
    if (task.status === 'running') {
      setBusy(true)
      setFeedback({ tone: 'neutral', text: 'Prediction is still running on the ML service. You can leave this page; it will continue in the background.' })
    } else if (task.status === 'completed' && task.result?.available) {
      setLatest(task.result)
      setActiveWindow('short')
      setBusy(false)
      setFeedback({ tone: 'healthy', text: `Prediction completed · ${horizon} steps · ${formatDateTime(task.result.created_at)}` })
      void load({ restore: false })
    } else if (task.status === 'failed') {
      setBusy(false)
      setError(task.error || 'Prediction request failed.')
    }
  }, [taskKey, taskVersion, horizon, load])
  useEffect(() => { load({ restore: true }) }, [load])
  useEffect(() => {
    const timer = window.setInterval(() => load({ restore: false }), 30000)
    return () => window.clearInterval(timer)
  }, [load])

  const changeSelection = (kind, value) => {
    setFeedback(null)
    setLatest(null)
    setActiveWindow('short')
    if (kind === 'machine') setMachineId(value)
    if (kind === 'signal') setSignal(value)
    if (kind === 'model') setModel(value)
    if (kind === 'horizon') setHorizon(Number(value))
  }

  const run = async () => {
    if (busy || taskBusy) return
    if (!canRun) {
      setFeedback({ tone: 'warning', text: `Need ${Math.max(0, minimum - samples)} more telemetry samples before this model can run.` })
      return
    }
    setBusy(true); setError(null); setFeedback({ tone: 'neutral', text: 'Prediction started. It will continue even if you leave Model Lab.' })
    try {
      await startPredictionTask({
        key: taskKey,
        run: () => api.get(`/api/predictions/machines/${machineId}/forecast?reading_type=${encodeURIComponent(signal)}&model=${encodeURIComponent(model)}&horizon=${horizon}`, { cache: 'no-store' }),
      })
    } catch (e) {
      setError(e?.message || 'Prediction request failed.')
      setBusy(false)
    }
  }

  const startNewPrediction = () => {
    if (taskBusy) return
    clearPredictionTask(taskKey)
    setLatest(null)
    setActiveWindow('short')
    setFeedback({ tone: 'neutral', text: 'Ready for a new prediction. Previous predictions remain saved in history.' })
    setError(null)
  }

  const openWindow = name => {
    const run = windows?.[name]
    if (!run?.available) return
    setActiveWindow(name)
    setLatest(run)
    setFeedback({ tone: 'healthy', text: `${WINDOW_LABELS[name]} automatic forecast loaded from saved prediction.` })
  }

  const openHistory = run => {
    setLatest(run)
    setActiveWindow(run.forecast_window || 'short')
    if (!run.forecast_window && run.horizon) setHorizon(Number(run.horizon))
    setFeedback({ tone: 'healthy', text: 'Saved prediction loaded from history.' })
  }

  if (loading && !lab) return <div className="panel"><div className="panel-body">Loading prediction system…</div></div>

  return <div className="model-lab-page">
    <section className="panel ml-hero">
      <div>
        <div className="ml-eyebrow"><BrainCircuit size={16} /> FORECAST WORKSPACE</div>
        <h2>{selectedLabel}</h2>
        <p>Persistent forecasts for the selected machine, signal and model. Saved results stay visible while telemetry refreshes in the background.</p>
      </div>
      <div className="ml-hero-actions"><Pill tone={status?.telemetry_active ? 'healthy' : 'warning'}>{status?.telemetry_active ? 'Telemetry live' : 'Telemetry stale · saved replay'}</Pill><Pill>{samples} samples</Pill><button className="btn secondary" type="button" onClick={() => load({ restore: false })}><RefreshCw size={14} /> Refresh</button></div>
    </section>

    <section className="panel">
      <div className="panel-header"><span className="panel-title">Forecast setup</span><Pill>{model === 'timer' ? 'Timer-Lite' : 'Chronos-Bolt-Tiny'} · production</Pill></div>
      <div className="panel-body ml-setup">
        <div className="ml-fields">
          <Field label="Machine" value={machineId} onChange={v => changeSelection('machine', v)}>{machines.map(m => <option key={m.machine_id} value={m.machine_id}>{m.machine_name || `Machine ${m.machine_id}`} · {m.machine_type || m.category || 'other'}</option>)}</Field>
          <Field label="Signal" value={signal} onChange={v => changeSelection('signal', v)}><option value="temperature">Temperature</option><option value="vibration">Vibration</option><option value="pressure">Pressure</option><option value="humidity">Humidity</option><option value="current">Current</option><option value="load">Load</option></Field>
          <Field label="Forecast model" value={model} onChange={v => changeSelection('model', v)}><option value="chronos-bolt-tiny">Chronos-Bolt-Tiny</option><option value="timer">Timer-Lite</option></Field>
        </div>
        <div className="ml-action-row">
          <Field label="Short horizon" value={String(horizon)} onChange={v => changeSelection('horizon', v)} hint="Restored when you return to the same selection.">{[6, 12, 24, 48].map(v => <option key={v} value={v}>{v} steps</option>)}</Field>
          <div className={`ml-readiness ${canRun ? 'ready' : ''}`}><Zap size={16} /><div><strong>{samples} / {minimum} samples ready</strong><small>{canRun ? 'Model is ready to run' : `Waiting for ${Math.max(0, minimum - samples)} more samples`}</small></div></div>
          <button className="btn primary ml-run" type="button" onClick={run} disabled={busy || taskBusy}>{busy || taskBusy ? <><Loader2 size={15} /> Running…</> : <><Play size={15} /> Run prediction</>}</button>
        </div>
        {feedback && <div className={`ml-feedback ${feedback.tone}`}><CheckCircle2 size={14} />{feedback.text}</div>}
        {error && <div className="ml-error">{error}</div>}
      </div>
    </section>

    <section className="panel ml-result">
      <div className="panel-header"><div><span className="panel-title">Forecast result</span><div className="ml-subtitle">{activeWindow !== 'short' ? `${WINDOW_LABELS[activeWindow]} automatic forecast` : `${horizon} step saved prediction`} · {selectedLabel} · {signal}</div></div><Pill tone={latest?.available ? 'healthy' : 'neutral'}>{latest?.available ? 'Saved' : 'No forecast selected'}</Pill></div>
      <div className="panel-body">
        {forecast.length ? <>
          <div className="ml-stats">
            <Stat icon={Target} label="NEXT" value={fmt(first)} sub="t+1" />
            <Stat icon={TrendingUp} label="END" value={fmt(last)} sub={`t+${forecast.length}`} />
            <Stat icon={total != null && total < 0 ? TrendingDown : TrendingUp} label="TREND" value={trend} sub={total == null ? 'no baseline' : `${total >= 0 ? '+' : ''}${fmt(total)} vs latest`} />
            <Stat icon={Activity} label="MODEL DELTA" value={baseline != null && first != null ? fmt(first - baseline) : '—'} sub="first step vs latest" />
          </div>
          <ForecastChart actual={actual} forecast={forecast} />
          <div className="ml-values">{forecast.slice(0, 12).map((value, i) => <div key={i}><strong>{fmt(value)}</strong><small>t+{i + 1}</small></div>)}</div>
        </> : <div className="ml-empty-result"><BrainCircuit size={22} /><strong>No saved forecast for this selection</strong><span>Run the short prediction once. The result will stay here and will be restored when you return to the same machine, signal and horizon.</span></div>}
      </div>
    </section>

    <section className="panel">
      <div className="panel-header"><div><span className="panel-title">Automatic outlook</span><div className="ml-subtitle">Generated from telemetry · saved per machine · no manual horizon execution</div></div><Pill>4 horizons</Pill></div>
      <div className="panel-body ml-horizons">{WINDOWS.map(name => <HorizonCard key={name} name={name} run={windows?.[name]} selected={activeWindow === name} onOpen={openWindow} />)}</div>
    </section>

    <section className="panel">
      <div className="panel-header"><div><span className="panel-title"><History size={15} /> Saved prediction history</span><div className="ml-subtitle">Persistent runs for {selectedLabel} · {signal} · {model}</div></div><Pill>{recentHistory.length} records</Pill></div>
      <div className="panel-body ml-history">{recentHistory.length ? recentHistory.map((run, i) => <HistoryItem key={run.run_id || `${run.created_at}-${i}`} run={run} onOpen={openHistory} />) : <div className="ml-history-empty">No saved predictions for this selection yet.</div>}</div>
    </section>

    <section className="panel">
      <div className="panel-body ml-notes"><div><strong><Gauge size={14} /> How to read the forecast</strong><p>Solid line = observed machine telemetry. Dashed line = model projection. This is a signal trajectory, not a failure probability; use it with degradation evidence, safety limits, maintenance history and technician inspection.</p></div><div className="ml-note-box">Automatic horizons are generated from telemetry and stored per machine. Timer-Lite stays on the lightweight inference path.</div></div>
    </section>
  </div>
}
