import { useEffect, useMemo, useState } from 'react'
import { Activity, BrainCircuit, Clock3, GitCompareArrows, Radio, RefreshCw } from 'lucide-react'
import api from '../api/client.js'
import { formatDateTime } from '../utils/dates.js'
import { usePageHeader } from '../PageHeaderContext.jsx'

const WINDOWS = ['24h', '48h', '7d', '30d']
const LABELS = { '24h': '24 hours', '48h': '48 hours', '7d': '7 days', '30d': '30 days' }
const fmt = value => value == null || Number.isNaN(Number(value)) ? '—' : Number(value).toFixed(2)

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
    setBusy(true); setError(null)
    try {
      const data = await api.get(`/api/predictions/machines/${machineId}/windows/compare?window=${windowName}&reading_type=${encodeURIComponent(readingType)}`)
      setResult(data)
    } catch (e) { setError(e?.message || 'Model comparison failed.') }
    finally { setBusy(false) }
  }

  const chronos = result?.models?.['chronos-bolt-tiny']?.run || result?.models?.['chronos-bolt-tiny'] || {}
  const timer = result?.models?.timer?.run || result?.models?.timer || {}

  return <>
    <div className="panel section-gap">
      <div className="panel-header"><span className="panel-title"><GitCompareArrows size={16}/> Model comparison</span><span className="badge neutral">On-demand · no automatic Timer calls</span></div>
      <div className="panel-body">
        <p style={{color:'var(--text-dim)',fontSize:13,lineHeight:1.6,marginTop:0}}>Compare the primary Chronos-Bolt-Tiny forecast with the secondary Timer model for the same machine, signal, telemetry snapshot, and horizon. Timer is intentionally opt-in so enabling comparison does not double inference load for the fleet.</p>
        <div className="grid-2" style={{marginBottom:12}}>
          <label>Machine<select value={machineId} onChange={e=>{setMachineId(e.target.value);setResult(null)}}>{machines.map(m=><option key={m.machine_id} value={m.machine_id}>{m.machine_name} · {m.category || 'other'}</option>)}</select></label>
          <label>Signal<select value={readingType} onChange={e=>{setReadingType(e.target.value);setResult(null)}}><option value="temperature">Temperature</option><option value="vibration">Vibration</option><option value="current">Motor Current</option><option value="load">Machine Load</option><option value="humidity">Humidity</option></select></label>
          <label>Forecast horizon<select value={windowName} onChange={e=>{setWindowName(e.target.value);setResult(null)}}>{WINDOWS.map(w=><option key={w} value={w}>{LABELS[w]}</option>)}</select></label>
          <div style={{display:'flex',alignItems:'end'}}><button className="btn" onClick={compare} disabled={busy || !machineId}>{busy ? <><RefreshCw size={14}/> Comparing…</> : <><BrainCircuit size={14}/> Compare models</>}</button></div>
        </div>
        <div className="chip-row"><span style={{fontSize:11,color:'var(--text-faint)'}}><Radio size={12}/> Selected machine: {selected?.machine_name || '—'}</span><span style={{fontSize:11,color:'var(--text-faint)'}}><Clock3 size={12}/> {LABELS[windowName]} uses the saved calendar-resolution forecast.</span></div>
      </div>
    </div>

    {error && <div className="panel section-gap"><div className="panel-body" style={{color:'var(--critical)',fontSize:12}}>{error}</div></div>}

    {result && <>
      <div className="stat-grid section-gap">
        <div className="stat-tile"><div className="stat-label"><BrainCircuit size={14}/> Chronos-Bolt-Tiny</div><div className="stat-value">{fmt(chronos.end_prediction)}</div><div style={{fontSize:11,color:'var(--text-faint)'}}>{chronos.trend || '—'} · endpoint</div></div>
        <div className="stat-tile"><div className="stat-label"><Activity size={14}/> Timer</div><div className="stat-value">{fmt(timer.end_prediction)}</div><div style={{fontSize:11,color:'var(--text-faint)'}}>{timer.trend || '—'} · endpoint</div></div>
        <div className="stat-tile"><div className="stat-label"><GitCompareArrows size={14}/> Endpoint delta</div><div className="stat-value">{fmt(result.comparison?.endpoint_delta)}</div><div style={{fontSize:11,color:'var(--text-faint)'}}>Timer − Chronos</div></div>
        <div className="stat-tile"><div className="stat-label"><Radio size={14}/> Agreement</div><div className="stat-value" style={{fontSize:18}}>{result.comparison?.same_direction == null ? '—' : result.comparison.same_direction ? 'Same trend' : 'Different trend'}</div><div style={{fontSize:11,color:'var(--text-faint)'}}>Directional comparison</div></div>
      </div>

      <div className="panel section-gap">
        <div className="panel-header"><span className="panel-title">Saved comparison · {selected?.machine_name || 'Machine'} · {LABELS[windowName]}</span><span className="badge neutral">{readingType}</span></div>
        <div className="panel-body">
          <div className="grid-2">
            {[['Chronos-Bolt-Tiny', chronos], ['Timer', timer]].map(([name, run]) => <div key={name} className="stat-tile"><div style={{fontWeight:700}}>{name}</div><div style={{marginTop:10,fontSize:12,color:'var(--text-dim)'}}>Next: <b>{fmt(run.next_prediction)}</b></div><div style={{fontSize:12,color:'var(--text-dim)'}}>End: <b>{fmt(run.end_prediction)}</b></div><div style={{fontSize:11,color:'var(--text-faint)',marginTop:6}}>Status: {run.status || (run.available ? 'completed' : 'unavailable')}</div><div style={{fontSize:10,color:'var(--text-faint)',marginTop:4}}>Saved: {run.created_at ? formatDateTime(run.created_at) : '—'}</div>{run.reason && <div style={{fontSize:11,color:'var(--warning)',marginTop:8}}>{run.reason}</div>}</div>)}
          </div>
          <div style={{marginTop:12,fontSize:11,color:'var(--text-faint)'}}>A model disagreement is evidence to investigate, not a failure verdict. Use it alongside telemetry quality, anomaly signals, thresholds, and maintenance history.</div>
        </div>
      </div>
    </>}
  </>
}
