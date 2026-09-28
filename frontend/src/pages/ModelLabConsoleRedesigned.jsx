import { useEffect, useMemo, useRef, useState } from 'react'
import { Activity, BrainCircuit, CheckCircle2, Clock3, Gauge, History, Loader2, Play, RefreshCw, Target, TrendingDown, TrendingUp, Zap } from 'lucide-react'
import api from '../api/client.js'
import { formatDateTime } from '../utils/dates.js'
import { usePageHeader } from '../PageHeaderContext.jsx'

const WINDOWS = ['24h', '48h', '7d', '30d']
const WINDOW_LABELS = { '24h': '24 hours', '48h': '48 hours', '7d': '7 days', '30d': '30 days' }
const WINDOW_STEPS = { '24h': '24 hourly points', '48h': '48 hourly points', '7d': '28 six-hour points', '30d': '30 daily points' }
const MIN = { 'chronos-bolt-tiny': 16, timer: 16 }
const fmt = (v, d = 2) => v == null || Number.isNaN(Number(v)) ? '—' : Number(v).toFixed(d)

function Pill({ children, tone = 'neutral' }) {
  return <span className={`badge ${tone}`}>{children}</span>
}

function SelectField({ label, value, onChange, children, hint }) {
  return <label style={{ display: 'grid', gap: 7 }}>
    <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '.07em' }}>{label}</span>
    <select value={value} onChange={e => onChange(e.target.value)} className="input" style={{ width: '100%', minHeight: 44, fontSize: 13, fontWeight: 650 }}>{children}</select>
    {hint && <span style={{ fontSize: 10, color: 'var(--text-faint)' }}>{hint}</span>}
  </label>
}

function Chart({ actual = [], forecast = [] }) {
  const history = actual.map(Number).filter(Number.isFinite).slice(-32)
  const future = forecast.map(Number).filter(Number.isFinite).slice(0, 48)
  const all = [...history, ...future]
  if (!all.length) return <div style={{ minHeight: 320, display: 'grid', placeItems: 'center', color: 'var(--text-faint)' }}>No saved forecast for this selection yet.</div>
  const width = 1000, height = 320
  const min = Math.min(...all), max = Math.max(...all), range = max - min || 1
  const count = history.length + future.length
  const x = i => (i / Math.max(count - 1, 1)) * width
  const y = v => height - 35 - ((v - min) / range) * (height - 70)
  const actualPoints = history.map((v, i) => `${x(i)},${y(v)}`).join(' ')
  const futurePoints = future.map((v, i) => `${x(history.length + i)},${y(v)}`).join(' ')
  const split = history.length ? x(history.length - 1) : 0
  return <div style={{ border: '1px solid var(--border)', borderRadius: 16, background: 'linear-gradient(180deg,var(--panel-raised),var(--panel))', overflow: 'hidden' }}>
    <div style={{ padding: '14px 16px 4px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12 }}>
      <div style={{ display: 'flex', gap: 16, alignItems: 'center', fontSize: 11, color: 'var(--text-dim)' }}>
        <span><i style={{ display: 'inline-block', width: 20, borderTop: '3px solid var(--accent)', marginRight: 6, verticalAlign: 'middle' }} />Observed</span>
        <span><i style={{ display: 'inline-block', width: 20, borderTop: '3px dashed var(--warning)', marginRight: 6, verticalAlign: 'middle' }} />Forecast</span>
      </div>
      <span style={{ fontSize: 10, color: 'var(--text-faint)' }}>recent telemetry → predicted future</span>
    </div>
    <svg viewBox={`0 0 ${width} ${height}`} width="100%" height="320" role="img" aria-label="Observed telemetry and forecast">
      {[55, 115, 175, 235, 295].map(gy => <line key={gy} x1="0" y1={gy} x2={width} y2={gy} stroke="var(--border)" strokeWidth="1" />)}
      {history.length > 1 && <line x1={split} y1="0" x2={split} y2={height} stroke="var(--text-faint)" strokeDasharray="5 7" />}
      {actualPoints && <polyline fill="none" stroke="var(--accent)" strokeWidth="4" strokeLinejoin="round" strokeLinecap="round" points={actualPoints} />}
      {futurePoints && <polyline fill="none" stroke="var(--warning)" strokeWidth="4" strokeDasharray="9 7" strokeLinejoin="round" strokeLinecap="round" points={futurePoints} />}
      <text x="12" y="22" fill="var(--text-faint)" fontSize="11">ACTUAL</text>
      {futurePoints && <text x={Math.min(split + 12, width - 110)} y="22" fill="var(--warning)" fontSize="11">FORECAST</text>}
    </svg>
    <div style={{ display: 'flex', justifyContent: 'space-between', padding: '0 16px 12px', color: 'var(--text-faint)', fontSize: 10 }}><span>Older telemetry</span><span>Now</span></div>
  </div>
}

function Stat({ icon: Icon, label, value, sub }) {
  return <div style={{ padding: '16px 17px', border: '1px solid var(--border)', borderRadius: 14, background: 'var(--panel-raised)', minWidth: 0 }}>
    <div style={{ display: 'flex', gap: 7, alignItems: 'center', color: 'var(--text-faint)', fontSize: 10, fontWeight: 800, letterSpacing: '.08em' }}><Icon size={13} />{label}</div>
    <div style={{ marginTop: 9, fontSize: 24, fontWeight: 800, letterSpacing: '-.03em', overflow: 'hidden', textOverflow: 'ellipsis' }}>{value}</div>
    <div style={{ marginTop: 3, fontSize: 10, color: 'var(--text-faint)' }}>{sub}</div>
  </div>
}

function Horizon({ name, run, selected, onSelect }) {
  const available = !!run?.available
  const running = run?.status === 'running' || !!run?.running
  return <button type="button" onClick={() => available && onSelect(name)} disabled={!available} style={{ width: '100%', minHeight: 132, textAlign: 'left', border: selected ? '1px solid var(--accent)' : '1px solid var(--border)', borderRadius: 14, background: selected ? 'color-mix(in srgb, var(--accent) 9%, var(--panel-raised))' : 'var(--panel-raised)', color: 'inherit', padding: 15, cursor: available ? 'pointer' : 'default', opacity: available ? 1 : .72, transition: 'border-color .15s, transform .15s' }}>
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 7, fontSize: 11, fontWeight: 750, color: 'var(--text-dim)' }}><Clock3 size={13} />{WINDOW_LABELS[name]}</div>
      <Pill tone={available ? 'healthy' : running ? 'neutral' : 'warning'}>{available ? 'Ready' : running ? 'Running' : 'Waiting'}</Pill>
    </div>
    {available ? <>
      <div style={{ marginTop: 13, fontSize: 21, fontWeight: 800 }}>{fmt(run.end_prediction)}</div>
      <div style={{ marginTop: 3, fontSize: 10, color: 'var(--text-faint)' }}>endpoint · {run.trend || 'Stable'} · {WINDOW_STEPS[name]}</div>
    </> : <>
      <div style={{ marginTop: 14, fontSize: 12, color: 'var(--text-faint)', minHeight: 34 }}>{run?.reason || 'Generated automatically when fresh telemetry is available.'}</div>
      <div style={{ marginTop: 8, fontSize: 10, color: 'var(--text-faint)' }}>Automatic · no manual run</div>
    </>}
  </button>
}

function HistoryItem({ run, onOpen }) {
  const usable = !!run?.available
  const label = run.forecast_window ? WINDOW_LABELS[run.forecast_window] || run.forecast_window : `${run.horizon || '—'} steps`
  return <button type="button" disabled={!usable} onClick={() => usable && onOpen(run)} style={{ width: '100%', border: '1px solid var(--border)', borderRadius: 11, background: 'var(--panel-raised)', color: 'inherit', padding: '12px 14px', textAlign: 'left', cursor: usable ? 'pointer' : 'default', opacity: usable ? 1 : .65 }}>
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 14 }}>
      <div><div style={{ fontWeight: 750, fontSize: 12 }}>{label} · {run.model || 'model'}</div><div style={{ marginTop: 3, fontSize: 10, color: 'var(--text-faint)' }}>{run.created_at ? formatDateTime(run.created_at) : '—'} · {run.trigger || 'automatic'}</div></div>
      <div style={{ textAlign: 'right' }}><div className="mono" style={{ fontWeight: 800 }}>{fmt(run.end_prediction)}</div><div style={{ marginTop: 2, fontSize: 10, color: 'var(--text-faint)' }}>{run.trend || run.status || 'saved'}</div></div>
    </div>
  </button>
}

export default function ModelLabConsoleRedesigned() {
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
  const [historyWindow, setHistoryWindow] = useState('short')
  const [busy, setBusy] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [feedback, setFeedback] = useState(null)
  const requestSeq = useRef(0)

  const machines = lab?.fleet?.machines || []
  const selected = useMemo(() => machines.find(m => String(m.machine_id) === String(machineId)), [machines, machineId])
  const samples = Number(status?.sample_count || 0)
  const minimum = Number(status?.minimum_samples || MIN[model] || 16)
  const activeWindow = historyWindow !== 'short' ? historyWindow : null
  const selectedLabel = selected?.machine_name || 'Machine'
  const currentForecast = latest?.forecast || []
  const canRun = !!machineId && samples >= minimum

  const load = async ({ preserve = true } = {}) => {
    const seq = ++requestSeq.current
    try {
      const data = await api.get('/api/analytics/model-lab')
      if (seq !== requestSeq.current) return
      setLab(data)
      const id = machineId || String(data?.fleet?.machines?.[0]?.machine_id || '')
      if (!id) { setLoading(false); return }
      if (!machineId) { setMachineId(id); return }
      const [s, h, readings, w] = await Promise.all([
        api.get(`/api/predictions/machines/${id}/status?reading_type=${encodeURIComponent(signal)}&model=${encodeURIComponent(model)}&horizon=${horizon}`),
        api.get(`/api/predictions/machines/${id}/history?reading_type=${encodeURIComponent(signal)}&model=${encodeURIComponent(model)}&limit=100`),
        api.get(`/api/machines/${id}/readings?limit=64`),
        api.get(`/api/predictions/machines/${id}/windows?reading_type=${encodeURIComponent(signal)}&model=${encodeURIComponent(model)}`),
      ])
      if (seq !== requestSeq.current) return
      const runs = (h?.runs || []).filter(Boolean)
      const exactShort = runs.find(r => r.available && !r.forecast_window && Number(r.horizon) === Number(horizon))
      const selectedWindow = activeWindow ? w?.windows?.[activeWindow] : null
      setStatus(s)
      setHistory(runs)
      setWindows(w?.windows || null)
      setActual((readings || []).filter(r => r.reading_type === signal).sort((a, b) => new Date(a.recorded_at) - new Date(b.recorded_at)).map(r => Number(r.value)).filter(Number.isFinite).slice(-32))
      if (!preserve || !latest) {
        setLatest(selectedWindow?.available ? selectedWindow : exactShort || (s?.latest_run?.available ? s.latest_run : null))
      } else if (activeWindow && selectedWindow?.available) {
        setLatest(selectedWindow)
      } else if (exactShort && !latest?.available) {
        setLatest(exactShort)
      }
      setError(null)
    } catch (e) {
      if (seq !== requestSeq.current) return
      setError(e?.message || 'Prediction center failed to load.')
    } finally {
      if (seq === requestSeq.current) setLoading(false)
    }
  }

  useEffect(() => { load({ preserve: false }); return undefined }, [machineId, signal, model, horizon, historyWindow])
  useEffect(() => {
    const t = window.setInterval(() => load({ preserve: true }), 30000)
    return () => window.clearInterval(t)
  }, [machineId, signal, model, horizon, historyWindow])

  const run = async () => {
    if (busy) return
    if (!canRun) {
      setFeedback({ tone: 'warning', text: `Need ${Math.max(0, minimum - samples)} more telemetry samples before this model can run.` })
      return
    }
    setBusy(true); setError(null); setFeedback(null)
    try {
      const result = await api.get(`/api/predictions/machines/${machineId}/forecast?reading_type=${encodeURIComponent(signal)}&model=${encodeURIComponent(model)}&horizon=${horizon}`)
      if (result?.available) setLatest(result)
      setFeedback(result?.available ? { tone: 'healthy', text: `Prediction saved · ${horizon} steps · ${formatDateTime(result.created_at)}` } : { tone: 'warning', text: result?.reason || 'Prediction was not generated.' })
      await load({ preserve: true })
    } catch (e) {
      setError(e?.message || 'Prediction request failed.')
    } finally { setBusy(false) }
  }

  const openWindow = name => {
    const run = windows?.[name]
    if (!run?.available) return
    setHistoryWindow(name); setLatest(run)
    setFeedback({ tone: 'healthy', text: `${WINDOW_LABELS[name]} automatic forecast loaded.` })
  }

  const openHistory = run => {
    if (!run?.available) return
    setLatest(run); setHistoryWindow(run.forecast_window || 'short')
    if (!run.forecast_window && run.horizon) setHorizon(Number(run.horizon))
    setFeedback({ tone: 'healthy', text: 'Saved prediction loaded from history.' })
  }

  if (loading && !lab) return <div className="panel"><div className="panel-body">Loading prediction system…</div></div>

  const baseline = actual.length ? Number(actual[actual.length - 1]) : null
  const first = currentForecast.length ? Number(currentForecast[0]) : null
  const last = currentForecast.length ? Number(currentForecast[currentForecast.length - 1]) : null
  const total = baseline != null && last != null ? last - baseline : null
  const trend = total == null || Math.abs(total) < 1e-6 ? 'Stable' : total > 0 ? 'Increasing' : 'Decreasing'
  const recentHistory = history.filter(r => r.available).slice(0, 8)
  const statusTone = status?.telemetry_active ? 'healthy' : 'warning'

  return <div style={{ display: 'grid', gap: 14 }}>
    <section className="panel" style={{ overflow: 'hidden' }}>
      <div className="panel-body" style={{ padding: 22 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 20, flexWrap: 'wrap' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 9, color: 'var(--accent)', fontSize: 11, fontWeight: 800, letterSpacing: '.08em' }}><BrainCircuit size={16} /> FORECAST WORKSPACE</div>
            <h2 style={{ margin: '8px 0 5px', fontSize: 25, letterSpacing: '-.03em' }}>{selectedLabel}</h2>
            <div style={{ color: 'var(--text-dim)', fontSize: 12 }}>Select a machine and signal, run a short forecast, and let the automatic horizons build from telemetry.</div>
          </div>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}><Pill tone={statusTone}>{status?.telemetry_active ? 'Telemetry live' : 'Telemetry stale · saved replay'}</Pill><Pill>{samples} samples</Pill><button className="btn secondary" type="button" onClick={() => load({ preserve: true })} title="Refresh model data"><RefreshCw size={14} /> Refresh</button></div>
        </div>
      </div>
    </section>

    <section className="panel">
      <div className="panel-header"><span className="panel-title">Forecast setup</span><Pill>{model === 'timer' ? 'Timer-Lite' : 'Chronos-Bolt-Tiny'} · production</Pill></div>
      <div className="panel-body" style={{ display: 'grid', gap: 18 }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr 1.15fr', gap: 14 }}>
          <SelectField label="Machine" value={machineId} onChange={v => { setMachineId(v); setLatest(null); setHistoryWindow('short') }}>
            {machines.map(m => <option key={m.machine_id} value={m.machine_id}>{m.machine_name || `Machine ${m.machine_id}`} · {m.machine_type || 'other'}</option>)}
          </SelectField>
          <SelectField label="Signal" value={signal} onChange={v => { setSignal(v); setLatest(null); setHistoryWindow('short') }}>
            <option value="temperature">Temperature</option><option value="vibration">Vibration</option><option value="pressure">Pressure</option><option value="humidity">Humidity</option>
          </SelectField>
          <SelectField label="Forecast model" value={model} onChange={v => { setModel(v); setLatest(null); setHistoryWindow('short') }}>
            <option value="chronos-bolt-tiny">Chronos-Bolt-Tiny</option><option value="timer">Timer-Lite</option>
          </SelectField>
        </div>
        <div style={{ display: 'flex', gap: 14, alignItems: 'end', flexWrap: 'wrap' }}>
          <SelectField label="Short horizon" value={String(horizon)} onChange={v => { setHorizon(Number(v)); setHistoryWindow('short') }} hint="Saved predictions are restored when you return to the same selection.">
            {[6, 12, 24, 48].map(v => <option key={v} value={v}>{v} steps</option>)}
          </SelectField>
          <div style={{ flex: 1, minWidth: 280, display: 'flex', alignItems: 'center', gap: 12, padding: '11px 13px', border: '1px solid var(--border)', borderRadius: 12, background: 'var(--panel-raised)', minHeight: 44 }}>
            <Zap size={15} style={{ color: canRun ? 'var(--accent)' : 'var(--text-faint)' }} />
            <div style={{ minWidth: 0 }}><div style={{ fontSize: 11, fontWeight: 750 }}>{samples} / {minimum} samples ready</div><div style={{ fontSize: 10, color: 'var(--text-faint)' }}>{canRun ? 'Model is ready to run' : `Waiting for ${Math.max(0, minimum - samples)} more samples`}</div></div>
          </div>
          <button className="btn primary" type="button" onClick={run} disabled={busy} style={{ minHeight: 44, minWidth: 154, justifyContent: 'center', opacity: busy ? .72 : 1 }}>
            {busy ? <><Loader2 size={15} className="spin" /> Running…</> : <><Play size={15} /> Run prediction</>}
          </button>
        </div>
        {feedback && <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 12px', borderRadius: 10, border: '1px solid var(--border)', color: feedback.tone === 'healthy' ? 'var(--success)' : 'var(--warning)', fontSize: 11 }}><CheckCircle2 size={14} />{feedback.text}</div>}
        {error && <div style={{ padding: '10px 12px', borderRadius: 10, border: '1px solid var(--border)', color: 'var(--danger)', fontSize: 11 }}>{error}</div>}
      </div>
    </section>

    <section className="panel">
      <div className="panel-header"><div><span className="panel-title">Forecast result</span><div style={{ marginTop: 4, fontSize: 10, color: 'var(--text-faint)' }}>{activeWindow ? `${WINDOW_LABELS[activeWindow]} automatic forecast` : `${horizon} step saved prediction`} · {selectedLabel} · {signal}</div></div><Pill tone={latest?.available ? 'healthy' : 'neutral'}>{latest?.available ? 'Saved' : 'No forecast selected'}</Pill></div>
      <div className="panel-body">
        {currentForecast.length ? <>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,minmax(0,1fr))', gap: 10, marginBottom: 12 }}>
            <Stat icon={Target} label="NEXT" value={fmt(first)} sub="t+1" />
            <Stat icon={TrendingUp} label="END" value={fmt(last)} sub={`t+${currentForecast.length}`} />
            <Stat icon={total != null && total < 0 ? TrendingDown : TrendingUp} label="TREND" value={trend} sub={total == null ? 'no baseline' : `${total >= 0 ? '+' : ''}${fmt(total)} vs latest`} />
            <Stat icon={Activity} label="MODEL DELTA" value={baseline != null && first != null ? fmt(first - baseline) : '—'} sub="first step vs latest" />
          </div>
          <Chart actual={actual} forecast={currentForecast} />
        </> : <div style={{ minHeight: 280, display: 'grid', placeItems: 'center', textAlign: 'center', padding: 30 }}><div><div style={{ width: 46, height: 46, borderRadius: 13, margin: '0 auto 12px', display: 'grid', placeItems: 'center', background: 'var(--panel-raised)', border: '1px solid var(--border)' }}><BrainCircuit size={20} /></div><div style={{ fontWeight: 750, fontSize: 14 }}>No saved forecast for this selection</div><div style={{ marginTop: 5, color: 'var(--text-faint)', fontSize: 11 }}>Run the short prediction once. The result will stay here and be restored when you return to the same machine, signal and horizon.</div></div></div>}
      </div>
    </section>

    <section className="panel">
      <div className="panel-header"><div><span className="panel-title">Automatic outlook</span><div style={{ marginTop: 4, fontSize: 10, color: 'var(--text-faint)' }}>Generated from telemetry · saved per machine · no manual horizon execution</div></div><Pill>4 horizons</Pill></div>
      <div className="panel-body" style={{ display: 'grid', gridTemplateColumns: 'repeat(4,minmax(0,1fr))', gap: 10 }}>
        {WINDOWS.map(name => <Horizon key={name} name={name} run={windows?.[name]} selected={activeWindow === name} onSelect={openWindow} />)}
      </div>
    </section>

    <section className="panel">
      <div className="panel-header"><div><span className="panel-title"><History size={15} style={{ verticalAlign: 'middle', marginRight: 6 }} />Saved prediction history</span><div style={{ marginTop: 4, fontSize: 10, color: 'var(--text-faint)' }}>Persistent runs for {selectedLabel} · {signal} · {model}</div></div><Pill>{recentHistory.length} shown</Pill></div>
      <div className="panel-body" style={{ display: 'grid', gap: 8 }}>
        {recentHistory.length ? recentHistory.map((run, i) => <HistoryItem key={run.run_id || `${run.created_at}-${i}`} run={run} onOpen={openHistory} />) : <div style={{ padding: 30, textAlign: 'center', color: 'var(--text-faint)', fontSize: 11 }}>No saved predictions for this selection yet.</div>}
      </div>
    </section>

    <section className="panel">
      <div className="panel-body" style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: 18, alignItems: 'start' }}>
        <div><div style={{ fontSize: 12, fontWeight: 800, marginBottom: 6 }}>How to read the forecast</div><div style={{ fontSize: 11, lineHeight: 1.65, color: 'var(--text-dim)' }}>The solid line is observed machine telemetry. The dashed line is the model's projected signal. A rising or falling forecast is a signal trajectory, not a failure probability. Use it with degradation evidence, safety limits, maintenance history and technician inspection.</div></div>
        <div style={{ padding: 13, borderRadius: 12, background: 'var(--panel-raised)', border: '1px solid var(--border)', fontSize: 11, color: 'var(--text-dim)' }}><div style={{ display: 'flex', gap: 7, alignItems: 'center', fontWeight: 800, color: 'var(--text)' }}><Gauge size={14} /> Lightweight inference</div><div style={{ marginTop: 5, lineHeight: 1.5 }}>Timer-Lite stays on its lightweight inference path so the Model Lab does not need to load the heavy checkpoint.</div></div>
      </div>
    </section>
  </div>
}
