import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import api from '../api/client.js'
import StatusBadge from './StatusBadge.jsx'
import { Loading, ErrorState } from '../pages/Dashboard.jsx'
import { usePageHeader } from '../PageHeaderContext.jsx'
import { getSpecializedMachineProfile, ROBOT_TYPES } from '../config/specializedMachineProfiles.js'

const norm = value => String(value ?? '').toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '')
const robotType = category => String(category || '').startsWith('robot_') ? String(category).slice(6) : null
const fmt = (value, unit = '') => {
  if (value == null || value === '') return '—'
  const numeric = Number(value)
  const rendered = Number.isFinite(numeric) ? numeric.toFixed(2) : value
  return unit ? `${rendered} ${unit}` : rendered
}

const SPECIALIZED_CSS = `
.sp{display:flex;flex-direction:column;gap:14px}
.sp-head{display:flex;align-items:center;gap:10px}
.sp-hero{padding:20px;border:1px solid var(--border);border-radius:16px;background:linear-gradient(135deg,rgba(59,130,246,.1),rgba(15,23,42,.15))}
.sp-kicker{text-transform:uppercase;letter-spacing:.12em;font-size:10px;color:var(--text-faint);font-weight:800}
.sp-title{font-size:25px;font-weight:850;margin:4px 0}
.sp-sub{font-size:12px;color:var(--text-faint)}
.sp-cards{display:grid;grid-template-columns:repeat(4,1fr);gap:9px;margin-top:16px}
.sp-card{padding:12px;border:1px solid var(--border);border-radius:10px}
.sp-card small{display:block;color:var(--text-faint);font-size:10px}
.sp-card strong{display:block;font-size:17px;margin:5px 0}
.sp-tabs{display:flex;gap:6px;overflow:auto}
.sp-tab{padding:9px 12px;border:1px solid var(--border);background:var(--panel);color:var(--text-dim);border-radius:9px;font-weight:700;cursor:pointer;white-space:nowrap}
.sp-tab.active{border-color:var(--accent);color:var(--text)}
.sp-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}
.sp-reading{border:1px solid var(--border);padding:11px;border-radius:9px}
.sp-reading small{display:block;color:var(--text-faint)}
.sp-reading strong{display:block;margin:4px 0}
.sp-layout{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.sp-list{display:flex;flex-direction:column}
.sp-row{display:flex;justify-content:space-between;gap:10px;padding:10px 0;border-bottom:1px solid var(--border);font-size:12px}
.sp-row:last-child{border-bottom:0}
.sp-components{display:grid;grid-template-columns:repeat(2,1fr);gap:8px}
.sp-component{border:1px solid var(--border);padding:12px;border-radius:9px;background:var(--panel);color:var(--text);text-align:left;cursor:pointer}
.sp-component.active{border-color:var(--accent)}
.sp-form{display:flex;gap:8px;flex-wrap:wrap;align-items:end}
.sp-form label{display:flex;flex-direction:column;gap:4px;font-size:10px;color:var(--text-faint);font-weight:700;min-width:120px;flex:1}
.sp-key{font-family:monospace;border:1px dashed var(--border);padding:10px;word-break:break-all;border-radius:8px;margin-top:8px}
.sp-note{padding:10px;border:1px solid var(--border);border-radius:8px;font-size:11px;color:var(--text-dim)}
.sp-actions{display:flex;gap:8px;flex-wrap:wrap;margin:10px 0}
.sp-muted{color:var(--text-faint);font-size:11px}
.sp-telemetry-status{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:11px 12px;border:1px solid var(--border);border-radius:10px;margin-bottom:10px}
.sp-telemetry-dot{width:8px;height:8px;border-radius:50%;display:inline-block;margin-right:7px;background:#64748b}
.sp-telemetry-dot.on{background:#34d399;box-shadow:0 0 8px rgba(52,211,153,.7)}
.sp-telemetry-dot.off{background:#f87171}
@media(max-width:850px){.sp-layout{grid-template-columns:1fr}.sp-cards{grid-template-columns:repeat(2,1fr)}.sp-grid{grid-template-columns:repeat(2,1fr)}}
@media(max-width:550px){.sp-components,.sp-grid{grid-template-columns:1fr}}
`

function Card({ label, value, sub }) {
  return <div className="sp-card"><small>{label}</small><strong>{value}</strong>{sub && <small>{sub}</small>}</div>
}

export default function SpecializedMachineDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [machine, setMachine] = useState(null)
  const [components, setComponents] = useState([])
  const [readings, setReadings] = useState([])
  const [maintenance, setMaintenance] = useState([])
  const [device, setDevice] = useState(null)
  const [safety, setSafety] = useState(null)
  const [intelligence, setIntelligence] = useState(null)
  const [degradation, setDegradation] = useState([])
  const [forecast, setForecast] = useState(null)
  const [forecastRuns, setForecastRuns] = useState([])
  const [tab, setTab] = useState('Overview')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState('')
  const [newComponent, setNewComponent] = useState('')
  const [selectedComponent, setSelectedComponent] = useState(null)
  const [sensors, setSensors] = useState([])
  const [componentReadings, setComponentReadings] = useState([])
  const [sensorForm, setSensorForm] = useState({ name: '', reading_type: '', unit: '', min_value: '', max_value: '' })
  const [componentReading, setComponentReading] = useState({ sensor_id: '', value: '', unit: '' })
  const [safetyPolicies, setSafetyPolicies] = useState([])
  const [safetySignal, setSafetySignal] = useState('')
  const [safetyForm, setSafetyForm] = useState({ enabled: true, warning_low: '', warning_high: '', shutdown_low: '', shutdown_high: '', auto_shutdown_enabled: false, unit: '' })
  const [deviceKey, setDeviceKey] = useState('')

  const load = async () => {
    setError(null)
    try {
      const machineData = await api.get(`/api/machines/${id}`)
      setMachine(machineData)
      const results = await Promise.allSettled([
        api.get(`/api/machines/${id}/components`),
        api.get(`/api/machines/${id}/readings?limit=200`),
        api.get(`/api/maintenance?machine_id=${id}&limit=100`),
        api.get(`/api/devices/${id}/status`),
        api.get(`/api/devices/${id}/safety`),
        api.get(`/api/analytics/machines/${id}/intelligence`),
        api.get(`/api/analytics/machines/${id}/degradation?limit=48`),
      ])
      if (results[0].status === 'fulfilled') setComponents(results[0].value || [])
      if (results[1].status === 'fulfilled') setReadings(results[1].value || [])
      if (results[2].status === 'fulfilled') setMaintenance(results[2].value || [])
      if (results[3].status === 'fulfilled') setDevice(results[3].value)
      if (results[4].status === 'fulfilled') {
        const currentSafety = results[4].value
        setSafety(currentSafety)
        setSafetyPolicies(currentSafety?.policies || [])
        const policy = (currentSafety?.policies || [])[0]
        if (policy) {
          setSafetySignal(policy.monitored_reading_type || '')
          setSafetyForm({
            ...policy,
            warning_low: policy.warning_low ?? '',
            warning_high: policy.warning_high ?? '',
            shutdown_low: policy.shutdown_low ?? '',
            shutdown_high: policy.shutdown_high ?? '',
            auto_shutdown_enabled: !!policy.auto_shutdown_enabled,
          })
        }
      }
      if (results[5].status === 'fulfilled') setIntelligence(results[5].value)
      if (results[6].status === 'fulfilled') setDegradation(results[6].value?.points || [])
    } catch (err) {
      setError(err.message || 'Unable to load machine')
    }
  }

  useEffect(() => { load() }, [id])

  useEffect(() => {
    const onTelemetry = event => {
      const data = event.detail
      if (String(data?.machine_id) !== String(id) || data.type !== 'telemetry') return
      setReadings(previous => [{ id: data.reading_id, reading_type: data.reading_type, value: data.value, unit: data.unit, recorded_at: data.recorded_at, source: 'live' }, ...previous].slice(0, 200))
      if (data.degradation) setDegradation(previous => [...previous, data.degradation].slice(-48))
    }
    window.addEventListener('maintain-ai-telemetry', onTelemetry)
    return () => window.removeEventListener('maintain-ai-telemetry', onTelemetry)
  }, [id])

  const profile = getSpecializedMachineProfile(machine?.category)
  const rtype = robotType(machine?.category)
  const live = useMemo(() => {
    const latest = {}
    for (const reading of readings) {
      const key = norm(reading.reading_type)
      if (!latest[key]) latest[key] = reading
    }
    return latest
  }, [readings])

  usePageHeader(<span className="sp-head"><button className="btn secondary" onClick={() => navigate('/machines')}>← Back</button>{machine?.name || 'Machine'}</span>, machine ? <StatusBadge status={machine.status} /> : null)

  const addComponent = async event => {
    event.preventDefault()
    if (!newComponent.trim()) return
    setBusy(true)
    try { await api.post(`/api/machines/${id}/components`, { name: newComponent.trim() }); setNewComponent(''); await load(); setNotice('Component saved.') } catch (err) { setNotice(err.message) } finally { setBusy(false) }
  }

  const selectComponent = async component => {
    setSelectedComponent(component)
    const results = await Promise.allSettled([api.get(`/api/components/${component.id}/sensors`), api.get(`/api/components/${component.id}/readings?limit=100`)])
    setSensors(results[0].status === 'fulfilled' ? results[0].value || [] : [])
    setComponentReadings(results[1].status === 'fulfilled' ? results[1].value || [] : [])
  }

  const addSensor = async event => {
    event.preventDefault(); if (!selectedComponent) return; setBusy(true)
    try { await api.post(`/api/components/${selectedComponent.id}/sensors`, { ...sensorForm, min_value: sensorForm.min_value === '' ? null : Number(sensorForm.min_value), max_value: sensorForm.max_value === '' ? null : Number(sensorForm.max_value) }); setSensorForm({ name: '', reading_type: '', unit: '', min_value: '', max_value: '' }); await selectComponent(selectedComponent); setNotice('Sensor registered for this component.') } catch (err) { setNotice(err.message) } finally { setBusy(false) }
  }

  const addComponentReading = async event => {
    event.preventDefault(); if (!selectedComponent) return; setBusy(true)
    try { await api.post(`/api/components/${selectedComponent.id}/readings`, { sensor_id: Number(componentReading.sensor_id), value: Number(componentReading.value), unit: componentReading.unit || null, source: 'manual' }); setComponentReading(previous => ({ ...previous, value: '' })); await selectComponent(selectedComponent); setNotice('Component reading persisted.') } catch (err) { setNotice(err.message) } finally { setBusy(false) }
  }

  const initialize = async () => {
    setBusy(true)
    try { for (const name of (profile.components || [])) if (!components.some(component => component.name === name)) await api.post(`/api/machines/${id}/components`, { name }); await load(); setNotice('Category engineering tree reconciled. Sensors remain real-device/manual inputs; no fake telemetry was generated.') } catch (err) { setNotice(err.message) } finally { setBusy(false) }
  }

  const provision = async () => {
    setBusy(true)
    try { const result = await api.post(`/api/devices/${id}/enable`, {}); setDevice(result); setDeviceKey(result.device_key || ''); setNotice('Live telemetry enabled. Connect the machine gateway/device using the displayed device key to begin sending real readings.') } catch (err) { setNotice(err.message) } finally { setBusy(false) }
  }

  const disableTelemetry = async () => {
    setBusy(true)
    try { const result = await api.post(`/api/devices/${id}/disable`, {}); setDevice(result); setDeviceKey(''); setNotice('Live telemetry disabled. The device key remains provisioned and can be enabled again when needed.') } catch (err) { setNotice(err.message) } finally { setBusy(false) }
  }

  const saveSafety = async () => {
    if (!safetySignal) { setNotice('Select a safety signal before saving.'); return }
    setBusy(true)
    try {
      const payload = { enabled: !!safetyForm.enabled, monitored_reading_type: safetySignal, unit: safetyForm.unit || null, warning_low: safetyForm.warning_low === '' ? null : Number(safetyForm.warning_low), warning_high: safetyForm.warning_high === '' ? null : Number(safetyForm.warning_high), shutdown_low: safetyForm.shutdown_low === '' ? null : Number(safetyForm.shutdown_low), shutdown_high: safetyForm.shutdown_high === '' ? null : Number(safetyForm.shutdown_high), auto_shutdown_enabled: !!safetyForm.auto_shutdown_enabled }
      const result = await api.put(`/api/devices/${id}/safety`, payload); setSafety(result); setSafetyPolicies(result.policies || []); setNotice('Safety policy persisted. Automatic shutdown is active only when this policy is explicitly enabled and an authenticated device is connected.')
    } catch (err) { setNotice(err.message) } finally { setBusy(false) }
  }

  const forecastRun = async () => {
    const signal = profile.predictions?.[0]
    const samples = readings.filter(reading => norm(reading.reading_type) === norm(signal))
    if (!signal || samples.length < 8) { setNotice(`Forecast requires at least 8 stored ${signal || 'prediction'} samples. Current samples: ${samples.length}. No synthetic forecast was created.`); return }
    setBusy(true)
    try {
      const result = await api.get(`/api/analytics/machines/${id}/forecast?reading_type=${encodeURIComponent(signal)}&model=chronos-bolt-tiny&horizon=12`); setForecast(result)
      try { const history = await api.get(`/api/predictions/machines/${id}/history?reading_type=${encodeURIComponent(signal)}&model=chronos-bolt-tiny&limit=20`); setForecastRuns(history.runs || []) } catch { setForecastRuns([]) }
      setNotice('Forecast completed. The result is based on stored telemetry; persisted run history is shown when available.')
    } catch (err) { setNotice(err.message) } finally { setBusy(false) }
  }

  if (error && !machine) return <ErrorState message={error} />
  if (!machine) return <Loading />

  const telemetry = profile.telemetry || []
  const hazards = profile.hazards || []
  const safetyProfiles = profile.safety || []

  return <><style>{SPECIALIZED_CSS}</style><main className="sp">
    <section className="sp-hero"><div className="sp-kicker">{profile.name}</div><div className="sp-title">{machine.name}</div><div className="sp-sub">{profile.subtitle} · {machine.machine_code} · {machine.location || 'Location not set'}</div>{rtype && <div style={{ marginTop: 12 }}><span className="sp-kicker">Robot architecture</span><div style={{ marginTop: 5, fontWeight: 800 }}>{ROBOT_TYPES.find(item => item.value === rtype)?.label || rtype}</div></div>}<div className="sp-cards"><Card label="Health" value={`${machine.health_score}/100`} sub="Machine record" /><Card label="Status" value={machine.status} sub="Current condition" /><Card label="Live signals" value={readings.filter(reading => reading.source === 'live').length} sub="Stored live events" /><Card label="Components" value={components.length} sub="Persisted parts" /></div></section>
    <nav className="sp-tabs">{['Overview','Components','Safety','Health','Predictions','Maintenance','Telemetry'].map(item => <button key={item} className={`sp-tab ${tab === item ? 'active' : ''}`} onClick={() => setTab(item)}>{item}</button>)}</nav>
    {notice && <div className="sp-note">{notice}</div>}

    {tab === 'Overview' && <div className="sp-layout"><section className="panel"><div className="panel-header"><span className="panel-title">Live engineering telemetry</span><small>Only actual stored/realtime readings appear</small></div><div className="panel-body sp-grid">{telemetry.map(([key,label,unit]) => <div className="sp-reading" key={key}><small>{label}</small><strong>{fmt(live[norm(key)]?.value, live[norm(key)]?.unit || unit)}</strong><small>{live[norm(key)]?.recorded_at || 'No sample yet'}</small></div>)}</div></section><section className="panel"><div className="panel-header"><span className="panel-title">Engineering hazards</span></div><div className="panel-body sp-list">{hazards.map(hazard => <div className="sp-row" key={hazard}><span>{hazard.replaceAll('_',' ')}</span><strong>Monitor / configure</strong></div>)}</div></section></div>}

    {tab === 'Components' && <section className="panel"><div className="panel-header"><span className="panel-title">{profile.name} component tree</span><small>Each part can own independent sensors and readings</small></div><div className="panel-body">{!components.length && <div className="sp-note">No components exist yet. Initialize the category model to create the engineering structure.</div>}<div className="sp-actions"><button className="btn" disabled={busy} onClick={initialize}>Initialize / reconcile engineering model</button><form className="sp-form" onSubmit={addComponent}><label>Custom component<input value={newComponent} onChange={event => setNewComponent(event.target.value)} placeholder="e.g. Gripper" /></label><button className="btn secondary" type="submit" disabled={busy}>Add</button></form></div><div className="sp-components">{components.map(component => <button key={component.id} className={`sp-component ${selectedComponent?.id === component.id ? 'active' : ''}`} onClick={() => selectComponent(component)}><strong>{component.name}</strong><small style={{display:'block',color:'var(--text-faint)',marginTop:4}}>Component #{component.id}</small></button>)}</div>{selectedComponent && <div style={{marginTop:14}}><div className="panel-header"><span className="panel-title">{selectedComponent.name} sensors</span></div><div className="sp-list">{sensors.map(sensor => <div className="sp-row" key={sensor.id}><span>{sensor.name}<small style={{display:'block',color:'var(--text-faint)'}}>{sensor.reading_type} · {sensor.unit || 'unitless'}</small></span><strong>{sensor.enabled ? 'Enabled' : 'Disabled'}</strong></div>)}</div><form className="sp-form" onSubmit={addSensor} style={{marginTop:10}}><label>Sensor name<input required value={sensorForm.name} onChange={event => setSensorForm({...sensorForm,name:event.target.value})}/></label><label>Reading type<input required value={sensorForm.reading_type} onChange={event => setSensorForm({...sensorForm,reading_type:event.target.value})}/></label><label>Unit<input value={sensorForm.unit} onChange={event => setSensorForm({...sensorForm,unit:event.target.value})}/></label><label>Min<input type="number" value={sensorForm.min_value} onChange={event => setSensorForm({...sensorForm,min_value:event.target.value})}/></label><label>Max<input type="number" value={sensorForm.max_value} onChange={event => setSensorForm({...sensorForm,max_value:event.target.value})}/></label><button className="btn" type="submit" disabled={busy}>Register sensor</button></form>{sensors.length > 0 && <form className="sp-form" onSubmit={addComponentReading} style={{marginTop:10}}><label>Sensor<select required value={componentReading.sensor_id} onChange={event => setComponentReading({...componentReading,sensor_id:event.target.value})}><option value="">Select sensor</option>{sensors.map(sensor => <option key={sensor.id} value={sensor.id}>{sensor.name} · {sensor.reading_type}</option>)}</select></label><label>Value<input required type="number" step="any" value={componentReading.value} onChange={event => setComponentReading({...componentReading,value:event.target.value})}/></label><label>Unit<input value={componentReading.unit} onChange={event => setComponentReading({...componentReading,unit:event.target.value})}/></label><button className="btn secondary" type="submit" disabled={busy}>Record reading</button></form>}<div className="sp-list" style={{marginTop:10}}>{componentReadings.map(reading => <div className="sp-row" key={reading.id}><span>{reading.reading_type}</span><strong>{fmt(reading.value,reading.unit)} · {reading.source}</strong></div>)}</div></div>}</div></section>}

    {tab === 'Safety' && <div className="sp-layout"><section className="panel"><div className="panel-header"><span className="panel-title">Operator-defined safety policies</span><small>Profile values are recommendations; saved policies are authoritative</small></div><div className="panel-body"><div className="sp-list">{safetyProfiles.map(item => <div className="sp-row" key={item.signal}><span>{item.label}<small style={{display:'block',color:'var(--text-faint)'}}>{item.signal} · warning {item.warning.join('–')} · shutdown {item.shutdown.join('–')}</small></span><button className="btn secondary" onClick={() => {setSafetySignal(item.signal);setSafetyForm({enabled:true,warning_low:item.warning[0],warning_high:item.warning[1],shutdown_low:item.shutdown[0],shutdown_high:item.shutdown[1],auto_shutdown_enabled:false,unit:''})}}>Use profile as starting point</button></div>)}</div>{safetySignal && <div style={{marginTop:12}}><div className="sp-note">Configure the limits for <b>{safetySignal}</b>. Saving creates or updates a persistent safety policy for this machine. Automatic shutdown stays OFF unless you explicitly enable it here.</div><div className="sp-grid" style={{marginTop:10}}>{[['warning_low','Warning low'],['warning_high','Warning high'],['shutdown_low','Shutdown low'],['shutdown_high','Shutdown high']].map(([key,label]) => <label className="field" key={key}><span>{label}</span><input type="number" step="any" value={safetyForm[key] ?? ''} onChange={event => setSafetyForm({...safetyForm,[key]:event.target.value})}/></label>)}</div><label style={{display:'flex',gap:8,marginTop:10}}><input type="checkbox" checked={!!safetyForm.enabled} onChange={event => setSafetyForm({...safetyForm,enabled:event.target.checked})}/> Enable threshold monitoring</label><label style={{display:'flex',gap:8,marginTop:10}}><input type="checkbox" checked={!!safetyForm.auto_shutdown_enabled} onChange={event => setSafetyForm({...safetyForm,auto_shutdown_enabled:event.target.checked})}/> Enable automatic shutdown for this policy</label><button className="btn" style={{marginTop:10}} disabled={busy} onClick={saveSafety}>Save safety policy</button></div>}</div></section><section className="panel"><div className="panel-header"><span className="panel-title">Actual safety state</span></div><div className="panel-body sp-list"><div className="sp-row"><span>Policies</span><strong>{safetyPolicies.length}</strong></div><div className="sp-row"><span>Threshold monitoring</span><strong>{safety?.enabled ? 'Enabled' : 'Not enabled'}</strong></div><div className="sp-row"><span>Automatic shutdown</span><strong>{safety?.auto_shutdown_enabled ? 'Enabled' : 'OFF'}</strong></div><div className="sp-note">Shutdown commands are evaluated against persisted policies when authenticated device telemetry arrives. The UI never fabricates a shutdown event.</div></div></section></div>}

    {tab === 'Health' && <div className="sp-layout"><section className="panel"><div className="panel-header"><span className="panel-title">Condition intelligence</span></div><div className="panel-body sp-list">{intelligence ? <><div className="sp-row"><span>Health score</span><strong>{machine.health_score}/100</strong></div><div className="sp-row"><span>Signals analyzed</span><strong>{intelligence.signal_count ?? intelligence.samples ?? '—'}</strong></div></> : <div className="sp-note">No intelligence summary is available yet. Feed real telemetry to populate it.</div>}</div></section><section className="panel"><div className="panel-header"><span className="panel-title">Degradation timeline</span></div><div className="panel-body"><div className="sp-list">{degradation.slice(-12).map((point,index) => <div className="sp-row" key={index}><span>{point.recorded_at || point.timestamp || 'sample'}</span><strong>{point.score ?? point.degradation_score ?? '—'}</strong></div>)}{!degradation.length && <div className="sp-note">Waiting for telemetry evidence.</div>}</div></div></section></div>}

    {tab === 'Predictions' && <div className="sp-layout"><section className="panel"><div className="panel-header"><span className="panel-title">Predictive maintenance</span><small>Uses real stored telemetry only</small></div><div className="panel-body"><div className="sp-row"><span>Primary signal</span><strong>{profile.predictions?.[0] || 'None configured'}</strong></div><div className="sp-row"><span>Available samples</span><strong>{readings.filter(reading => norm(reading.reading_type) === norm(profile.predictions?.[0])).length}</strong></div><button className="btn" disabled={busy} onClick={forecastRun}>Run forecast</button>{forecast && <pre style={{whiteSpace:'pre-wrap',fontSize:11,marginTop:10}}>{JSON.stringify(forecast,null,2)}</pre>}</div></section><section className="panel"><div className="panel-header"><span className="panel-title">Forecast history</span></div><div className="panel-body sp-list">{forecastRuns.map((run,index) => <div className="sp-row" key={run.id || index}><span>{run.created_at || run.timestamp || 'run'}</span><strong>{run.status || run.model || 'completed'}</strong></div>)}{!forecastRuns.length && <div className="sp-note">No persisted forecast runs are shown yet.</div>}</div></section></div>}

    {tab === 'Maintenance' && <section className="panel"><div className="panel-header"><span className="panel-title">Maintenance history</span><small>Existing maintenance records are preserved</small></div><div className="panel-body sp-list">{maintenance.map(item => <div className="sp-row" key={item.id}><span>{item.type} · {item.description || 'Maintenance'}</span><strong>{item.status}</strong></div>)}{!maintenance.length && <div className="sp-note">No maintenance records for this machine.</div>}</div></section>}

    {tab === 'Telemetry' && <div className="sp-layout"><section className="panel"><div className="panel-header"><span className="panel-title">Device integration</span><small>Controls whether authenticated machine telemetry is accepted</small></div><div className="panel-body sp-list"><div className="sp-telemetry-status"><span><span className={`sp-telemetry-dot ${device?.iot_enabled ? 'on' : 'off'}`}></span>Live telemetry</span><strong>{device?.iot_enabled ? 'ON' : 'OFF'}</strong></div><div className="sp-row"><span>IoT integration</span><strong>{device?.iot_enabled ? 'Enabled' : 'Disabled'}</strong></div><div className="sp-row"><span>Device key</span><strong>{device?.has_key ? 'Provisioned' : 'Not provisioned'}</strong></div><div className="sp-actions"><button className="btn" disabled={busy} onClick={device?.iot_enabled ? disableTelemetry : provision}>{device?.iot_enabled ? 'Disable live telemetry' : 'Enable live telemetry & provision device'}</button>{device?.iot_enabled && <button className="btn secondary" disabled={busy} onClick={provision}>Regenerate device key</button>}</div>{deviceKey && <div className="sp-key">{deviceKey}</div>}<div className="sp-note">Enabling this switch only authorizes the machine gateway. Actual values appear here only after a real authenticated device sends telemetry with the device key.</div></div></section><section className="panel"><div className="panel-header"><span className="panel-title">Live machine telemetry</span><small>{readings.filter(reading => reading.source === 'live').length} stored live events in current view</small></div><div className="panel-body sp-grid">{telemetry.map(([key,label,unit]) => <div className="sp-reading" key={key}><small>{label}</small><strong>{fmt(live[norm(key)]?.value,live[norm(key)]?.unit || unit)}</strong><small>{live[norm(key)]?.recorded_at || 'Waiting for a real device sample'}</small></div>)}</div></section></div>}
  </main></>
}
