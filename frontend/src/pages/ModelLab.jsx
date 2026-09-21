import { useEffect, useMemo, useState } from 'react'
import { BrainCircuit, Radio, ShieldCheck, Timer, TrendingUp, ChevronRight } from 'lucide-react'
import api from '../api/client.js'
import { formatDateTime } from '../utils/dates.js'
import { usePageHeader } from '../PageHeaderContext.jsx'

const fmt = (v) => v == null ? '—' : Number(v).toFixed(3)

function Status({ ok, children }) {
  return <span className={'badge ' + (ok ? 'healthy' : 'warning')}>{children}</span>
}

export default function ModelLab() {
  usePageHeader('AI Monitoring / Model Lab')
  const [data, setData] = useState(null)
  const [evidence, setEvidence] = useState(null)
  const [error, setError] = useState(null)
  const [selectedMachine, setSelectedMachine] = useState(null)
  const [machineEvidence, setMachineEvidence] = useState(null)
  const [machineBusy, setMachineBusy] = useState(false)

  const load = async () => {
    try {
      const [lab, ev] = await Promise.all([
        api.get('/api/analytics/model-lab'),
        api.get('/api/analytics/evidence-feed?limit=80'),
      ])
      setData(lab); setEvidence(ev); setError(null)
    } catch (e) { setError(e.message) }
  }

  useEffect(() => {
    load()
    const timer = window.setInterval(load, 15000)
    return () => window.clearInterval(timer)
  }, [])

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
        <div className="panel-body"><p style={{color:'var(--text-dim)',fontSize:13,margin:0}}>This page shows model availability and evidence health. It does not convert anomaly signals into unsupported failure probabilities.</p></div>
      </div>

      <div className="stat-grid">
        {cards.map(({icon:Icon,title,value,detail}) => <div className="stat-tile" key={title}><div className="stat-label"><Icon size={14} style={{verticalAlign:'-3px',marginRight:5}} />{title}</div><div className="stat-value" style={{fontSize:22}}>{value}</div><div style={{color:'var(--text-faint)',fontSize:11,marginTop:5}}>{detail}</div></div>)}
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
              <div><b>Forecasts:</b> signal-value forecasting only; not failure probabilities</div>
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

      <div className="panel">
        <div className="panel-header"><span className="panel-title">Unified Evidence Feed</span><span className="badge neutral">Point-in-time records</span></div>
        <div className="panel-body">
          {evidence?.events?.length ? <div style={{display:'grid',gap:7}}>{evidence.events.map((e,i) => <div key={e.id + '-' + i} style={{display:'grid',gridTemplateColumns:'150px 110px 1fr',gap:10,padding:'9px 0',borderBottom:'1px solid var(--border)',fontSize:12}}><span className="mono" style={{color:'var(--text-faint)'}}>{formatDateTime(e.timestamp)}</span><span className="badge neutral">{e.type}</span><span><b>{e.machine_name}</b> · {e.message}</span></div>)}</div> : <div className="empty-state">No evidence records yet.</div>}
        </div>
      </div>

      <div className="panel section-gap">
        <div className="panel-header"><span className="panel-title">Interpretation Rules</span><ShieldCheck size={16}/></div>
        <div className="panel-body" style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(220px,1fr))',gap:10}}>
          {[['Anomaly ≠ failure','Anomaly models detect unusual temporal behaviour; they do not prove a future failure.'],['Forecast ≠ failure','Chronos-2 and Timer forecast signal values, not component failure.'],['Risk readiness ≠ risk','Label counts tell us whether supervised risk training is supportable.'],['Safety ≠ ML','Safety thresholds remain explicit supervisory controls and must not depend on an unvalidated model.']].map(([title,body]) => <div key={title} style={{padding:12,border:'1px solid var(--border)',borderRadius:10,background:'var(--panel-raised)'}}><b>{title}</b><div style={{color:'var(--text-dim)',fontSize:12,lineHeight:1.5,marginTop:5}}>{body}</div></div>)}
        </div>
      </div>
    </>
  )
}
