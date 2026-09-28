import { useEffect, useMemo, useState } from 'react'
import { Activity, BrainCircuit, Clock3, GitCompareArrows, Radio, RefreshCw } from 'lucide-react'
import api from '../api/client.js'
import { formatDateTime } from '../utils/dates.js'
import { usePageHeader } from '../PageHeaderContext.jsx'

const WINDOWS = ['24h', '48h', '7d', '30d']
const LABELS = { '24h': '24 hours', '48h': '48 hours', '7d': '7 days', '30d': '30 days' }
const fmt = value => value == null || Number.isNaN(Number(value)) ? '—' : Number(value).toFixed(2)

function ComparisonChart({ chronos = [], timer = [] }) {
  const a = chronos.map(Number).filter(Number.isFinite)
  const b = timer.map(Number).filter(Number.isFinite)
  const values = [...a, ...b]
  if (!values.length) return <div className="empty-state">No saved forecast values are available for this comparison.</div>
  const min = Math.min(...values)
  const max = Math.max(...values)
  const range = max - min || 1
  const width = 860
  const height = 250
  const count = Math.max(a.length, b.length, 1)
  const point = (value, index) => `${(index / Math.max(count - 1, 1)) * width},${height - 20 - ((value - min) / range) * (height - 40)}`
  const aPoints = a.map(point).join(' ')
  const bPoints = b.map(point).join(' ')
  return <div style={{ overflowX:'auto', background:'var(--panel-raised)', border:'1px solid var(--border)', borderRadius:10, padding:10 }}>
    <svg viewBox={`0 0 ${width} ${height}`} width="100%" height="250" role="img" aria-label="Chronos-Bolt-Tiny and Timer forecast comparison">
      <line x1="0" y1="65" x2={width} y2="65" stroke="var(--border)" />
      <line x1="0" y1="125" x2={width} y2="125" stroke="var(--border)" />
      <line x1="0" y1="185" x2={width} y2="185" stroke="var(--border)" />
      {aPoints && <polyline fill="none" stroke="var(--accent)" strokeWidth="3" points={aPoints} />}
      {bPoints && <polyline fill="none" stroke="var(--warning)" strokeWidth="3" strokeDasharray="7 5" points={bPoints} />}
      <text x="8" y="18" fill="var(--accent)" fontSize="11">Chronos-Bolt-Tiny</text>
      <text x="150" y="18" fill="var(--warning)" fontSize="11">Timer</text>
      <text x="8" y={height - 5} fill="var(--text-faint)" fontSize="10">t+1</text>
      <text x={width - 40} y={height - 5} fill="var(--text-faint)" fontSize="10">end</text>
    </svg>
  </div>
}

function ModelCard({ name, run, tone }) {
  const forecast = Array.isArray(run?.forecast) ? run.forecast : []
  return <div className="stat-tile" style={{ minHeight: 190 }}>
    <div style={{ display:'flex', justifyContent:'space-between', gap:8, alignItems:'center' }}>
      <div style={{ fontWeight:700 }}>{name}</div>
      <span className={'badge ' + (run?.available ? 'healthy' : 'warning')}>{run?.available ? 'Available' : 'Unavailable'}</span>
    </div>
    <div style={{ marginTop:14, fontSize:12, color:'var(--text-dim)' }}>Next value <b>{fmt(run?.next_prediction)}</b></div>
    <div style={{ fontSize:12, color:'var(--text-dim)', marginTop:5 }}>Endpoint <b>{fmt(run?.end_prediction)}</b></div>
    <div style={{ fontSize:12, color:'var(--text-dim)', marginTop:5 }}>Trend <b>{run?.trend || '—'}</b></div>
    <div style={{ fontSize:10, color:'var(--text-faint)', marginTop:8 }}>{run?.created_at ? `Saved ${formatDateTime(run.created_at)}` : 'No saved run'}</div>
    {forecast.length > 0 && <div style={{ marginTop:10, fontSize:10, color: tone }}>{forecast.length} forecast points · same selected machine/signal/window</div>}
    {run?.reason && <div style={{ marginTop:10, fontSize:11, color:'var(--warning)' }}>{run.reason}</div>}
  </div>
}

export default function ModelComparison() {
  usePageHeader('AI Monitoring / Model Comparison')
  const [lab, setLab] = useState(null)
  const [machineId, setMachineId] = useState('')
  const [readingType, setReadingType] = useState('temperature')
  const [windowName, setWindowName] = useState('24h')
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  const machines = lab?.fleet?.machines || []
  const selected = useMemo(() => machines.find(m => String(m.machine_id) === String(machineId)), [machines, machineId])

  const loadMachines = async () => {
    try {
      const data = await api.get('/api/analytics/model-lab')
      setLab(data)
      if (!machineId && data?.fleet?.machines?.[0]?.machine_id != null) setMachineId(String(data.fleet.machines[0].machine_id))
    } catch (e) { setError(e?.message || 'Could not load machines.') }
  }

  useEffect(() => { loadMachines() }, [])

  const compare = async () => {
    if (!machineId) return
    setBusy(true)
    setError(null)
    try {
      const data = await api.get(`/api/predictions/machines/${machineId}/windows/compare?window=${windowName}&reading_type=${encodeURIComponent(readingType)}`)
      setResult(data)
    } catch (e) { setError(e?.message || 'Model comparison failed.') }
    finally { setBusy(false) }
  }

  const chronos = result?.models?.['chronos-bolt-tiny']?.run || result?.models?.['chronos-bolt-tiny'] || {}
  const timer = result?.models?.timer?.run || result?.models?.timer || {}
  const chronosForecast = Array.isArray(chronos?.forecast) ? chronos.forecast : []
  const timerForecast = Array.isArray(timer?.forecast) ? timer.forecast : []

  return <>
    <div className="panel section-gap" style={{ border:'1px solid var(--accent)', boxShadow:'0 0 28px rgba(0,200,255,.06)' }}>
      <div className="panel-header">
        <span className="panel-title"><GitCompareArrows size={16}/> Model comparison workspace</span>
        <span className="badge neutral">Chronos-Bolt-Tiny + Timer</span>
      </div>
      <div className="panel-body">
        <p style={{ color:'var(--text-dim)', fontSize:13, lineHeight:1.65, marginTop:0 }}>
          This is an investigation tool, not a second automatic forecasting pipeline. It runs both models against the <b>same machine, signal, telemetry snapshot and horizon</b>, then lets you inspect where their predicted trajectories agree or diverge. Timer remains opt-in so normal fleet forecasting does not double the ML workload.
        </p>
        <div className="grid-2" style={{ marginBottom:12 }}>
          <label>Machine<select value={machineId} onChange={e=>{setMachineId(e.target.value);setResult(null)}}>{machines.map(m=><option key={m.machine_id} value={m.machine_id}>{m.machine_name} · {m.category || 'other'}</option>)}</select></label>
          <label>Signal<select value={readingType} onChange={e=>{setReadingType(e.target.value);setResult(null)}}><option value="temperature">Temperature</option><option value="vibration">Vibration</option><option value="current">Motor Current</option><option value="load">Machine Load</option><option value="humidity">Humidity</option></select></label>
          <label>Forecast horizon<select value={windowName} onChange={e=>{setWindowName(e.target.value);setResult(null)}}>{WINDOWS.map(w=><option key={w} value={w}>{LABELS[w]}</option>)}</select></label>
          <div style={{ display:'flex', alignItems:'end' }}><button className="btn" onClick={compare} disabled={busy || !machineId}>{busy ? <><RefreshCw size={14}/> Comparing…</> : <><GitCompareArrows size={14}/> Compare models</>}</button></div>
        </div>
        <div className="chip-row">
          <span style={{ fontSize:11, color:'var(--text-faint)' }}><Radio size={12}/> Machine: {selected?.machine_name || '—'}</span>
          <span style={{ fontSize:11, color:'var(--text-faint)' }}><Clock3 size={12}/> Horizon: {LABELS[windowName]}</span>
          <span style={{ fontSize:11, color:'var(--text-faint)' }}><Activity size={12}/> Comparison is saved/reused per telemetry snapshot</span>
        </div>
      </div>
    </div>

    {error && <div className="panel section-gap"><div className="panel-body" style={{ color:'var(--critical)', fontSize:12 }}>{error}</div></div>}

    {result && <>
      <div className="stat-grid section-gap">
        <div className="stat-tile"><div className="stat-label"><BrainCircuit size={14}/> Chronos-Bolt-Tiny</div><div className="stat-value">{fmt(chronos.end_prediction)}</div><div style={{ fontSize:11, color:'var(--text-faint)' }}>{chronos.trend || '—'} · endpoint</div></div>
        <div className="stat-tile"><div className="stat-label"><Activity size={14}/> Timer</div><div className="stat-value">{fmt(timer.end_prediction)}</div><div style={{ fontSize:11, color:'var(--text-faint)' }}>{timer.trend || '—'} · endpoint</div></div>
        <div className="stat-tile"><div className="stat-label"><GitCompareArrows size={14}/> Endpoint delta</div><div className="stat-value">{fmt(result.comparison?.endpoint_delta)}</div><div style={{ fontSize:11, color:'var(--text-faint)' }}>Timer − Chronos</div></div>
        <div className="stat-tile"><div className="stat-label"><Radio size={14}/> Direction</div><div className="stat-value" style={{ fontSize:18 }}>{result.comparison?.same_direction == null ? '—' : result.comparison.same_direction ? 'Agree' : 'Diverge'}</div><div style={{ fontSize:11, color:'var(--text-faint)' }}>Endpoint trend direction</div></div>
      </div>

      <div className="panel section-gap">
        <div className="panel-header"><span className="panel-title">Forecast trajectories</span><span className="badge neutral">{selected?.machine_name || 'Machine'} · {LABELS[windowName]} · {readingType}</span></div>
        <div className="panel-body">
          <ComparisonChart chronos={chronosForecast} timer={timerForecast} />
          <div style={{ marginTop:12, fontSize:12, color:'var(--text-dim)', lineHeight:1.6 }}>
            <b>How to read it:</b> the solid trajectory is Chronos-Bolt-Tiny and the dashed trajectory is Timer. Close trajectories indicate similar signal forecasts for this snapshot; widening trajectories indicate model disagreement that should be investigated against telemetry quality, operating conditions and maintenance evidence.
          </div>
        </div>
      </div>

      <div className="grid-2 section-gap">
        <ModelCard name="Chronos-Bolt-Tiny · primary" run={chronos} tone="var(--accent)" />
        <ModelCard name="Timer · secondary" run={timer} tone="var(--warning)" />
      </div>

      <div className="panel section-gap">
        <div className="panel-header"><span className="panel-title">Comparison record</span><span className="badge neutral">Same input snapshot</span></div>
        <div className="panel-body">
          <div className="grid-2">
            <div style={{ padding:12, borderRadius:8, background:'var(--panel-raised)', border:'1px solid var(--border)', fontSize:12, color:'var(--text-dim)' }}>
              <div style={{ color:'var(--text-faint)', fontSize:10 }}>INPUT</div>
              <div style={{ marginTop:5 }}><b>{selected?.machine_name || 'Machine'}</b> · {readingType} · {LABELS[windowName]}</div>
              <div style={{ marginTop:5 }}>Both models receive the same prepared time-series snapshot.</div>
            </div>
            <div style={{ padding:12, borderRadius:8, background:'var(--panel-raised)', border:'1px solid var(--border)', fontSize:12, color:'var(--text-dim)' }}>
              <div style={{ color:'var(--text-faint)', fontSize:10 }}>INTERPRETATION</div>
              <div style={{ marginTop:5 }}>A difference between models is <b>evidence to investigate</b>, not a failure verdict or probability.</div>
              <div style={{ marginTop:5 }}>Saved results can be revisited without automatically rerunning inference on the same telemetry snapshot.</div>
            </div>
          </div>
        </div>
      </div>
    </>}
  </>
}
