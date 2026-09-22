import { useEffect, useState, useMemo } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import api, { getToken, clearApiCache } from '../api/client.js'
import { formatDateTime, formatDate } from '../utils/dates.js'
import StatusBadge from '../components/StatusBadge.jsx'
import { Loading, ErrorState } from './Dashboard.jsx'
import { usePageHeader } from '../PageHeaderContext.jsx'
import { useAuth } from '../AuthContext.jsx'

export default function MachineDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { user } = useAuth()
  const canEdit = user?.role === 'admin'
  const [machine, setMachine] = useState(null)
  const [components, setComponents] = useState([])
  const [readings, setReadings] = useState([])
  const [maintenance, setMaintenance] = useState([])
  const [error, setError] = useState(null)
  const [newReading, setNewReading] = useState({ reading_type: 'temperature', value: '', unit: '°C' })
  const [newComponent, setNewComponent] = useState('')
  const [deviceStatus, setDeviceStatus] = useState(null)
  const [deviceBusy, setDeviceBusy] = useState(false)
  const [deviceError, setDeviceError] = useState(null)
  const [revealedKey, setRevealedKey] = useState(null)
  const [liveReadings, setLiveReadings] = useState({})
  const [liveHistory, setLiveHistory] = useState({})
  const [liveConnected, setLiveConnected] = useState(false)
  const [intelligence, setIntelligence] = useState(null)
  const [safety, setSafety] = useState(null)
  const [safetyForm, setSafetyForm] = useState({ enabled: false, monitored_reading_type: 'temperature', unit: '°C', warning_low: '', warning_high: '', shutdown_low: '', shutdown_high: '', auto_shutdown_enabled: false })
  const [safetyPolicies, setSafetyPolicies] = useState([])
  const safetyDefaults = { temperature: { label: 'Temperature', unit: '°C', warningLow: 10, warningHigh: 40, shutdownLow: 5, shutdownHigh: 45 }, vibration: { label: 'Vibration', unit: 'g', warningLow: 0.8, warningHigh: 2, shutdownLow: 0, shutdownHigh: 3 }, current: { label: 'Motor Current', unit: 'A', warningLow: 1, warningHigh: 8, shutdownLow: 0, shutdownHigh: 12 }, load: { label: 'Machine Load', unit: '%', warningLow: 10, warningHigh: 80, shutdownLow: 5, shutdownHigh: 95 }, humidity: { label: 'Humidity', unit: '%', warningLow: 10, warningHigh: 70, shutdownLow: 5, shutdownHigh: 85 } }
  const [safetyBusy, setSafetyBusy] = useState(false)
  const [safetyEvent, setSafetyEvent] = useState(null)
  const [forecast, setForecast] = useState(null)
  const [forecastModel, setForecastModel] = useState('chronos2')
  const [forecastBusy, setForecastBusy] = useState(false)
  const [degradationTimeline, setDegradationTimeline] = useState([])

  usePageHeader(
    <span style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
      <button className="btn secondary" onClick={() => navigate('/machines')}>← Back</button>
      {machine?.name || 'Machine'}
    </span>,
    machine ? <StatusBadge status={machine.status} /> : null
  )

  const load = async () => {
    setError(null)
    setMachine(null)
    try {
      // Load the critical machine record first so one slow optional endpoint
      // can never keep the whole page on the skeleton.
      const m = await api.get(`/api/machines/${id}`)
      setMachine(m)
    } catch (e) {
      setError(e.message)
      return
    }

    const optional = await Promise.allSettled([
      api.get(`/api/machines/${id}/components`),
      api.get(`/api/machines/${id}/readings?limit=20`),
      api.get(`/api/maintenance?machine_id=${id}&limit=50`),
      api.get(`/api/devices/${id}/status`),
    ])

    const [componentsResult, readingsResult, maintenanceResult, deviceResult] = optional
    if (componentsResult.status === 'fulfilled') setComponents(componentsResult.value)
    if (readingsResult.status === 'fulfilled') setReadings(readingsResult.value)
    if (maintenanceResult.status === 'fulfilled') setMaintenance(maintenanceResult.value)
    if (deviceResult.status === 'fulfilled') setDeviceStatus(deviceResult.value)
    try { setIntelligence(await api.get(`/api/analytics/machines/${id}/intelligence`)) } catch { setIntelligence(null) }
    try { const d = await api.get(`/api/analytics/machines/${id}/degradation?limit=48`); setDegradationTimeline(d.points || []) } catch { setDegradationTimeline([]) }
    try { const s = await api.get(`/api/devices/${id}/safety`); setSafety(s); if (s.configured) { setSafetyPolicies(s.policies || [s]); setSafetyForm({ ...s, warning_low: s.warning_low ?? '', warning_high: s.warning_high ?? '', shutdown_low: s.shutdown_low ?? '', shutdown_high: s.shutdown_high ?? '' }) } } catch { setSafety(null) }
  }

  useEffect(() => {
    load()
  }, [id])

  useEffect(() => {
    if (!machine) return
    const refresh = window.setInterval(async () => {
      try { setIntelligence(await api.get(`/api/analytics/machines/${id}/intelligence`)) } catch { /* telemetry may be offline */ }
    }, 15000)
    return () => window.clearInterval(refresh)
  }, [id, machine])

  // Live telemetry is delivered through the tenant-scoped Supabase Realtime
  // channel established by App.jsx/realtime.js. Do not open a second process-local
  // backend WebSocket here: serverless instances are not guaranteed to share the
  // in-memory telemetry fan-out.
  useEffect(() => {
    const handleStatus = (event) => {
      const status = event?.detail
      setLiveConnected(status === 'connected')
    }
    const handleTelemetry = (event) => {
      const message = event?.detail
      if (!message || message.type !== 'telemetry' || String(message.machine_id) !== String(id)) return
      const reading = { value: Number(message.value), unit: message.unit || '', recorded_at: message.recorded_at }
      setLiveReadings(prev => ({ ...prev, [message.reading_type]: reading }))
      setLiveHistory(prev => ({ ...prev, [message.reading_type]: [...(prev[message.reading_type] || []), reading.value].slice(-24) }))
      if (message.safety) setSafetyEvent(message.safety)
      if (message.degradation) setDegradationTimeline(prev => [...prev, message.degradation].slice(-48))
      setLiveConnected(true)
    }
    window.addEventListener('maintain-ai-realtime-status', handleStatus)
    window.addEventListener('maintain-ai-telemetry', handleTelemetry)
    return () => {
      window.removeEventListener('maintain-ai-realtime-status', handleStatus)
      window.removeEventListener('maintain-ai-telemetry', handleTelemetry)
    }
  }, [id])

  const liveSensors = useMemo(() => ([
    ['temperature', 'Temperature', '°C'], ['vibration', 'Vibration', 'g'],
    ['current', 'Current', 'A'], ['load', 'Load', '%'], ['humidity', 'Humidity', '%']
  ].map(([key, label, fallbackUnit]) => ({ key, label, reading: liveReadings[key], unit: liveReadings[key]?.unit || fallbackUnit, history: liveHistory[key] || [] }))), [liveReadings, liveHistory])

  const addReading = async (e) => {
    e.preventDefault()
    await api.post(`/api/machines/${id}/readings`, { ...newReading, value: Number(newReading.value) })
    setNewReading({ ...newReading, value: '' })
    clearApiCache(`/api/machines/${id}`)
    load()
  }

  const addComponent = async (e) => {
    e.preventDefault()
    if (!newComponent.trim()) return
    await api.post(`/api/machines/${id}/components`, { name: newComponent })
    setNewComponent('')
    clearApiCache(`/api/machines/${id}`)
    load()
  }

  const runForecast = async () => {
    setForecastBusy(true)
    try { setForecast(await api.get('/api/analytics/machines/' + id + '/forecast?reading_type=temperature&model=' + forecastModel + '&horizon=12')) }
    finally { setForecastBusy(false) }
  }

  const saveSafety = async (e) => {
    e.preventDefault()
    setSafetyBusy(true)
    try {
      const payload = { ...safetyForm, unit: safetyDefaults[safetyForm.monitored_reading_type]?.unit || safetyForm.unit, warning_low: safetyForm.warning_low === '' ? null : Number(safetyForm.warning_low), warning_high: safetyForm.warning_high === '' ? null : Number(safetyForm.warning_high), shutdown_low: safetyForm.shutdown_low === '' ? null : Number(safetyForm.shutdown_low), shutdown_high: safetyForm.shutdown_high === '' ? null : Number(safetyForm.shutdown_high) }
      const saved = await api.put('/api/devices/' + id + '/safety', payload)
      setSafety(saved)
      setSafetyPolicies(saved.policies || [saved])
    } finally { setSafetyBusy(false) }
  }

  const selectSafetySignal = (type) => {
    const existing = safetyPolicies.find(p => p.monitored_reading_type === type)
    const d = safetyDefaults[type]
    setSafetyForm(existing ? { ...existing, warning_low: existing.warning_low ?? '', warning_high: existing.warning_high ?? '', shutdown_low: existing.shutdown_low ?? '', shutdown_high: existing.shutdown_high ?? '' } : { enabled: true, monitored_reading_type: type, unit: d.unit, warning_low: d.warningLow, warning_high: d.warningHigh, shutdown_low: d.shutdownLow, shutdown_high: d.shutdownHigh, auto_shutdown_enabled: safetyForm.auto_shutdown_enabled })
  }

  const testSafetyShutdown = async () => {
    setSafetyBusy(true)
    try { await api.post('/api/devices/' + id + '/safety/test-shutdown', {}) } finally { setSafetyBusy(false) }
  }
  const enableDevice = async () => {
    setDeviceBusy(true)
    setDeviceError(null)
    try {
      const result = await api.post(`/api/devices/${id}/enable`, {})
      if (!result?.device_key) throw new Error('Backend enabled live sensor integration but did not return a device key.')
      setRevealedKey(result.device_key)
      setDeviceStatus({ iot_enabled: result.iot_enabled, has_key: result.has_key })
    } catch (e) {
      setDeviceError(e?.message || 'Could not enable live sensor integration.')
    } finally {
      setDeviceBusy(false)
    }
  }

  const disableDevice = async () => {
    setDeviceBusy(true)
    setDeviceError(null)
    try {
      const result = await api.post(`/api/devices/${id}/disable`, {})
      setDeviceStatus(result)
      setRevealedKey(null)
    } catch (e) {
      setDeviceError(e?.message || 'Could not disable live sensor integration.')
    } finally {
      setDeviceBusy(false)
    }
  }

  if (error) return <ErrorState message={error} />
  if (!machine) return <Loading />

  return (
    <>
      <div className="stat-grid">
        <div className="stat-tile"><div className="stat-label">HEALTH SCORE</div><div className={`stat-value ${machine.status}`}>{machine.health_score}/100</div></div>
        <div className="stat-tile"><div className="stat-label">OPERATING HOURS</div><div className="stat-value">{machine.operating_hours}</div></div>
        <div className="stat-tile"><div className="stat-label">CRITICALITY</div><div className="stat-value">{machine.criticality}</div></div>
        <div className="stat-tile"><div className="stat-label">NEXT MAINTENANCE</div><div className="stat-value" style={{ fontSize: 15 }}>{machine.next_maintenance_date ? formatDate(machine.next_maintenance_date) : '—'}</div></div>
      </div>

      <div className="panel section-gap">
        <div className="panel-header">
          <span className="panel-title">Live Sensor Integration (Optional)</span>
          {deviceStatus?.iot_enabled && <span className="badge healthy">Enabled</span>}
        </div>
        <div className="panel-body">
          <p style={{ color: 'var(--text-dim)', fontSize: 13, marginBottom: 12 }}>
            Manual entry above always works, with or without this. Enabling this lets an ESP32
            (or any device) push readings directly for this machine over the network — see
            <code style={{ margin: '0 4px' }}>firmware/esp32_example.ino</code>
            for working example code. Off by default; nothing changes unless you turn it on.
          </p>

          {deviceError && <div style={{ marginBottom: 12, padding: 10, borderRadius: 8, background: 'rgba(255,70,70,.10)', color: 'var(--critical)', fontSize: 12 }}>{deviceError}</div>}

          {!canEdit && <div style={{ marginBottom: 12, color: 'var(--text-faint)', fontSize: 12 }}>Live sensor integration is managed by administrators.</div>}

          {revealedKey && (
            <div style={{ padding: 12, background: 'var(--panel-raised)', borderRadius: 8, marginBottom: 12 }}>
              <div style={{ fontSize: 12, color: 'var(--warning)', marginBottom: 6 }}>
                Copy this now — it's shown only once. Paste it into the firmware's DEVICE_KEY.
              </div>
              <div className="mono" style={{ fontSize: 13, wordBreak: 'break-all' }}>{revealedKey}</div>
            </div>
          )}

          {canEdit && deviceStatus?.iot_enabled ? (
            <div className="chip-row">
              <button className="btn secondary" onClick={enableDevice} disabled={deviceBusy}>
                {deviceBusy ? 'Working…' : 'Regenerate Key'}
              </button>
              <button className="btn danger" onClick={disableDevice} disabled={deviceBusy}>
                {deviceBusy ? 'Working…' : 'Disable'}
              </button>
            </div>
          ) : canEdit ? (
            <button className="btn" onClick={enableDevice} disabled={deviceBusy}>
              {deviceBusy ? 'Working…' : 'Enable Live Sensor Integration'}
            </button>
          ) : null}
        </div>
      </div>

      <div className="panel section-gap">
        <div className="panel-header">
          <span className="panel-title">Pretrained Signal Forecast</span>
          <span className="badge neutral">Zero-shot</span>
        </div>
        <div className="panel-body">
          <div className="chip-row">
            <select value={forecastModel} onChange={e=>setForecastModel(e.target.value)}>
              <option value="chronos2">Chronos-2</option>
              <option value="timer">Timer</option>
            </select>
            <button className="btn secondary" onClick={runForecast} disabled={forecastBusy}>{forecastBusy ? 'Forecasting…' : 'Forecast Temperature'}</button>
          </div>
          {forecast && <div style={{ marginTop: 12 }}>
            {forecast.available ? (
              <div className="mono" style={{ display:'grid', gridTemplateColumns:'repeat(6,minmax(0,1fr))', gap:8 }}>
                {forecast.forecast.slice(0,12).map((v,i)=><div key={i} style={{ padding:8, background:'var(--panel-raised)', borderRadius:6 }}>{Number(v).toFixed(2)}<div style={{fontSize:10,color:'var(--text-faint)'}}>t+{i+1}</div></div>)}
              </div>
            ) : <div style={{color:'var(--text-faint)',fontSize:12}}>{forecast.reason || 'Forecast unavailable.'}</div>}
          </div>}
          <div style={{ marginTop: 9, color:'var(--text-faint)', fontSize:11 }}>Forecasts estimate future sensor values. They are evidence for degradation analysis, not failure probabilities.</div>
        </div>
      </div>

      <div className="panel section-gap">
        <div className="panel-header">
          <span className="panel-title">Degradation Timeline</span>
          <span className="badge neutral">Online evidence · not failure probability</span>
        </div>
        <div className="panel-body">
          {degradationTimeline.length ? (
            <>
              <div style={{display:'flex',alignItems:'end',gap:3,height:120}}>
                {degradationTimeline.slice(-48).map((p,i) => (
                  <div key={p.recorded_at + i} title={`${p.recorded_at} · score ${Number(p.degradation_score).toFixed(3)}`} style={{flex:1,minWidth:2,height:`${8 + Number(p.degradation_score)*100}px`,maxHeight:110,borderRadius:2,background:'var(--accent)',opacity:0.25 + Number(p.degradation_score)*0.75}} />
                ))}
              </div>
              <div style={{display:'flex',justifyContent:'space-between',marginTop:8,color:'var(--text-faint)',fontSize:11}}>
                <span>{formatDateTime(degradationTimeline[0].recorded_at)}</span>
                <span>Latest: {Number(degradationTimeline[degradationTimeline.length-1].degradation_score).toFixed(3)}</span>
              </div>
              <div style={{marginTop:10,color:'var(--text-faint)',fontSize:11}}>
                Evidence combines live sensor anomaly deviation and multi-sensor agreement. It is intentionally not presented as a calibrated failure risk.
              </div>
            </>
          ) : <div className="empty-state">Collecting telemetry for the first degradation points…</div>}
        </div>
      </div>

      <div className="panel section-gap">
        <div className="panel-header">
          <span className="panel-title">Machine Safety Limits & Auto-Shutdown</span>
          <span className={'badge ' + (safety?.enabled ? 'healthy' : 'neutral')}>{safety?.enabled ? 'Monitoring' : 'Off'}</span>
        </div>
        <div className="panel-body">
          <p style={{ color: 'var(--text-dim)', fontSize: 13, marginBottom: 12 }}>Configure early warning points and hard shutdown points for one telemetry signal. Automatic shutdown is separately controlled and requires a connected safety-capable IoT device.</p>
          {canEdit && <form onSubmit={saveSafety}>
            <div className="chip-row" style={{ marginBottom: 10 }}>
              <label><input type="checkbox" checked={!!safetyForm.enabled} onChange={e => setSafetyForm({...safetyForm, enabled:e.target.checked})} /> Enable limit monitoring</label>
              <label>Signal <select value={safetyForm.monitored_reading_type} onChange={e => setSafetyForm({...safetyForm, monitored_reading_type:e.target.value})}><option value="temperature">Temperature</option><option value="vibration">Vibration</option><option value="current">Current</option><option value="load">Load</option></select></label>
              <label>Unit <input style={{width:70}} value={safetyForm.unit || ''} onChange={e => setSafetyForm({...safetyForm, unit:e.target.value})} /></label>
            </div>
            <div className="grid-2" style={{ marginBottom: 10 }}>
              <label>Warning low <input type="number" step="any" value={safetyForm.warning_low} onChange={e=>setSafetyForm({...safetyForm,warning_low:e.target.value})} /></label>
              <label>Warning high <input type="number" step="any" value={safetyForm.warning_high} onChange={e=>setSafetyForm({...safetyForm,warning_high:e.target.value})} /></label>
              <label>Shutdown low <input type="number" step="any" value={safetyForm.shutdown_low} onChange={e=>setSafetyForm({...safetyForm,shutdown_low:e.target.value})} /></label>
              <label>Shutdown high <input type="number" step="any" value={safetyForm.shutdown_high} onChange={e=>setSafetyForm({...safetyForm,shutdown_high:e.target.value})} /></label>
            </div>
            <div className="chip-row">
              <label><input type="checkbox" checked={!!safetyForm.auto_shutdown_enabled} onChange={e=>setSafetyForm({...safetyForm,auto_shutdown_enabled:e.target.checked})} /> Enable automatic shutdown command</label>
              <button className="btn" type="submit" disabled={safetyBusy}>{safetyBusy ? 'Saving…' : 'Save Safety Settings'}</button>
              <button className="btn secondary" type="button" onClick={testSafetyShutdown} disabled={safetyBusy || !deviceStatus?.iot_enabled}>Test IoT Shutdown Signal</button>
            </div>
          </form>}
          {!canEdit && <div style={{color:'var(--text-faint)',fontSize:12,marginTop:8}}>Safety settings are managed by administrators.</div>}
          <div style={{ marginTop: 10, color: 'var(--text-faint)', fontSize: 11 }}>The app sends a shutdown command to the authenticated IoT safety channel when a hard limit is crossed. For real equipment, the ESP32 should drive a properly rated relay/contactor or independent safety interlock locally; do not use a hobby GPIO as the sole protection for mains or hazardous machinery.</div>
          {safetyEvent && <div style={{ marginTop: 10, padding: 10, borderRadius: 8, background: safetyEvent.shutdown_requested ? 'rgba(255,70,70,.10)' : 'rgba(255,180,0,.10)', color: safetyEvent.shutdown_requested ? 'var(--critical)' : 'var(--warning)', fontSize: 12 }}>{safetyEvent.message}{safetyEvent.shutdown_requested ? ' · Shutdown command issued.' : ' · Warning notification issued.'}</div>}
        </div>
      </div>
      <div className="panel section-gap">
        <div className="panel-header">
          <span className="panel-title">Pretrained AI Signal</span>
          <span className={'badge ' + (intelligence?.pretrained_anomaly?.available ? 'healthy' : 'warning')}>
            {intelligence?.pretrained_anomaly?.available ? 'Zero-shot' : 'Not ready'}
          </span>
        </div>
        <div className="panel-body">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 16 }}>
            <div>
              <div style={{ color: 'var(--text-dim)', fontSize: 12 }}>Time-series anomaly model</div>
              <div className="mono" style={{ fontSize: 22, fontWeight: 700, marginTop: 4 }}>
                {intelligence?.pretrained_anomaly?.available ? Number(intelligence.pretrained_anomaly.anomaly_score).toFixed(3) : '—'}
              </div>
            </div>
            <div style={{ maxWidth: 520, color: 'var(--text-faint)', fontSize: 12 }}>
              {intelligence?.pretrained_anomaly?.available ? 'Pretrained zero-shot anomaly score from live telemetry. This is not a calibrated failure probability.' : (intelligence?.pretrained_anomaly?.reason || 'Waiting for pretrained model / telemetry.')}
            </div>
          </div>
        </div>
      </div>

      <div className="grid-2 section-gap">
        <div className="panel">
          <div className="panel-header"><span className="panel-title">Machine Info</span></div>
          <div className="panel-body">
            <InfoRow label="Machine code" value={machine.machine_code} mono />
            <InfoRow label="Category" value={machine.category} />
            <InfoRow label="Manufacturer" value={machine.manufacturer} />
            <InfoRow label="Model" value={machine.model_number} />
            <InfoRow label="Location" value={machine.location} />
            <InfoRow label="Department" value={machine.department} />
            <InfoRow label="Maintenance interval" value={`${machine.maintenance_interval_hours} hrs`} />
          </div>
        </div>

        <div className="panel">
          <div className="panel-header"><span className="panel-title">Components</span></div>
          <div className="panel-body">
            {components.map((c) => <div key={c.id} style={{ padding: '6px 0', borderBottom: '1px solid var(--border)' }}>{c.name}</div>)}
            {components.length === 0 && <div className="empty-state" style={{ padding: '8px 0' }}>No components logged yet.</div>}
            {canEdit && <form onSubmit={addComponent} style={{ display: 'flex', gap: 8, marginTop: 12 }}>
              <input value={newComponent} onChange={(e) => setNewComponent(e.target.value)} placeholder="e.g. Drive-end bearing" />
              <button className="btn secondary" type="submit">Add</button>
            </form>}
          </div>
        </div>
      </div>

      <div className="grid-2">
        <div className="panel">
          <div className="panel-header"><span className="panel-title">Sensor / Manual Readings</span></div>
          <div className="panel-body">
            {canEdit && <form onSubmit={addReading} style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
              <select value={newReading.reading_type} onChange={(e) => setNewReading({ ...newReading, reading_type: e.target.value })}>
                <option value="temperature">Temperature</option>
                <option value="vibration">Vibration</option>
                <option value="current">Current</option>
                <option value="load">Load</option>
              </select>
              <input type="number" step="any" required placeholder="value" value={newReading.value} onChange={(e) => setNewReading({ ...newReading, value: e.target.value })} />
              <input style={{ width: 70 }} value={newReading.unit} onChange={(e) => setNewReading({ ...newReading, unit: e.target.value })} />
              <button className="btn secondary" type="submit">Log</button>
            </form>}
            <table>
              <thead><tr><th>Type</th><th>Value</th><th>Recorded</th></tr></thead>
              <tbody>
                {readings.slice(0, 8).map((r) => (
                  <tr key={r.id}><td>{r.reading_type}</td><td className="mono">{r.value} {r.unit}</td><td className="mono">{formatDateTime(r.recorded_at)}</td></tr>
                ))}
                {readings.length === 0 && <tr><td colSpan={3} className="empty-state">No readings logged yet.</td></tr>}
              </tbody>
            </table>
          </div>
        </div>

        <div className="panel" style={{ border: '1px solid var(--accent)', boxShadow: '0 0 24px rgba(0, 200, 255, 0.08)' }}>
          <div className="panel-header">
            <span className="panel-title">Live Readings <span style={{ color: 'var(--text-faint)', fontWeight: 400 }}>(Real-time)</span></span>
            <span className={'badge ' + (liveConnected ? 'healthy' : 'warning')}>
              <span style={{ display: 'inline-block', width: 6, height: 6, borderRadius: '50%', background: 'currentColor', marginRight: 5 }} />
              {liveConnected ? 'Live' : 'Reconnecting'}
            </span>
          </div>
          <div className="panel-body">
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 10 }}>
              {liveSensors.map(sensor => <LiveSensorCard key={sensor.key} {...sensor} />)}
            </div>
            <div style={{ marginTop: 12, fontSize: 11, color: 'var(--text-faint)', textAlign: 'right' }}>
              {Object.keys(liveReadings).length ? 'Live telemetry received' : 'Waiting for device telemetry…'}
            </div>
          </div>
        </div>

        <div className="panel">
          <div className="panel-header"><span className="panel-title">Maintenance History</span></div>
          <table>
            <thead><tr><th>Type</th><th>Status</th><th>Scheduled</th></tr></thead>
            <tbody>
              {maintenance.map((r) => (
                <tr key={r.id}><td>{r.type}</td><td><StatusBadge status={r.status === 'completed' ? 'healthy' : r.status === 'overdue' ? 'critical' : 'warning'} /></td><td className="mono">{r.scheduled_date ? formatDate(r.scheduled_date) : '—'}</td></tr>
              ))}
              {maintenance.length === 0 && <tr><td colSpan={3} className="empty-state">No maintenance history yet.</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
    </>
  )
}

function LiveSensorCard({ label, reading, unit, history }) {
  const latest = reading?.value
  const previous = history.length > 1 ? history[history.length - 2] : null
  const delta = latest != null && previous != null ? latest - previous : null
  const direction = delta == null || Math.abs(delta) < 0.000001 ? '→' : delta > 0 ? '↑' : '↓'
  return (
    <div style={{ padding: 12, borderRadius: 10, background: 'var(--panel-raised)', border: '1px solid var(--border)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 7 }}><span style={{ color: 'var(--text-dim)', fontSize: 12 }}>{label}</span><span style={{ color: 'var(--accent)' }}>{direction}</span></div>
      <div className="mono" style={{ fontSize: 20, fontWeight: 700 }}>{latest == null || Number.isNaN(latest) ? '—' : latest + ' ' + unit}</div>
      <div style={{ height: 22, display: 'flex', alignItems: 'end', gap: 2, marginTop: 8 }}>
        {history.length ? history.slice(-16).map((value, index, arr) => { const min=Math.min(...arr), max=Math.max(...arr), range=max-min||1; return <span key={index} style={{ flex: 1, height: (5 + ((value-min)/range)*17) + 'px', borderRadius: 2, background: 'var(--accent)', opacity: 0.35 + index/arr.length*0.65 }} /> }) : <span style={{ color: 'var(--text-faint)', fontSize: 10 }}>No live samples yet</span>}
      </div>
    </div>
  )
}

function InfoRow({ label, value, mono }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', borderBottom: '1px solid var(--border)' }}>
      <span style={{ color: 'var(--text-faint)' }}>{label}</span>
      <span className={mono ? 'mono' : ''}>{value || '—'}</span>
    </div>
  )
}
