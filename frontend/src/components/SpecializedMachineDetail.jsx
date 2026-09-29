import { useEffect, useMemo, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import api, { clearApiCache } from '../api/client.js'
import StatusBadge from '../components/StatusBadge.jsx'
import { Loading, ErrorState } from '../pages/Dashboard.jsx'
import { usePageHeader } from '../PageHeaderContext.jsx'

const CATEGORY_LABELS = {
  cnc: 'CNC Machine', robot: 'Robot', drill_press: 'Drill Press', grinding_machine: 'Grinding Machine',
  hydraulic_press: 'Hydraulic Press', injection_molding: 'Injection Molding Machine', packaging_machine: 'Packaging Machine',
  generator: 'Generator', transformer: 'Transformer', boiler: 'Boiler', furnace: 'Furnace / Oven', hvac: 'HVAC Unit',
  fan_blower: 'Fan / Blower', gearbox: 'Gearbox', turbine: 'Turbine', crane_hoist: 'Crane / Hoist', agv_amr: 'AGV / AMR',
  water_treatment: 'Water Treatment System', other: 'Other Machine',
}

const SPECS = {
  cnc: { subtitle: 'Precision machining center', tabs: ['Overview', 'Axes & Spindle', 'Tooling', 'Components', 'Health'], panels: [['Axes', ['X axis', 'Y axis', 'Z axis', 'A axis', 'B axis']], ['Spindle', ['RPM', 'Temperature', 'Vibration', 'Load']], ['Tooling', ['Active tool', 'Tool life', 'Tool changer', 'Coolant']], ['Control', ['Program', 'Feed rate', 'Cycle time', 'Controller']]] },
  robot: { subtitle: 'Industrial robotic workcell', tabs: ['Overview', 'Motion', 'Components', 'Safety', 'Health'], panels: [['Motion system', ['Joint 1', 'Joint 2', 'Joint 3', 'Joint 4', 'Joint 5', 'Joint 6']], ['End effector', ['Gripper', 'Tool status', 'Grip force', 'Tool change']], ['Controller', ['Program', 'Controller temp', 'Servo status', 'Cycle count']], ['Safety', ['Emergency stop', 'Safety gate', 'Light curtain', 'Safe speed']]] },
  drill_press: { subtitle: 'Drilling and boring equipment', tabs: ['Overview', 'Spindle', 'Feed', 'Components', 'Health'], panels: [['Spindle', ['RPM', 'Temperature', 'Vibration', 'Load']], ['Feed', ['Feed rate', 'Depth', 'Force', 'Cycle time']], ['Workholding', ['Chuck', 'Clamp pressure', 'Tool', 'Coolant']]] },
  grinding_machine: { subtitle: 'Precision grinding equipment', tabs: ['Overview', 'Grinding', 'Wheel', 'Components', 'Health'], panels: [['Grinding', ['Spindle RPM', 'Grinding load', 'Vibration', 'Temperature']], ['Wheel', ['Wheel speed', 'Wheel life', 'Dressing', 'Balance']], ['Coolant', ['Flow', 'Temperature', 'Pressure', 'Level']]] },
  hydraulic_press: { subtitle: 'Hydraulic forming and pressing system', tabs: ['Overview', 'Hydraulics', 'Ram', 'Components', 'Safety'], panels: [['Hydraulics', ['Pressure', 'Oil temperature', 'Flow', 'Pump load']], ['Ram', ['Position', 'Force', 'Speed', 'Cycle']], ['Safety', ['Pressure relief', 'Guarding', 'Emergency stop', 'Limit switches']]] },
  injection_molding: { subtitle: 'Plastic injection molding system', tabs: ['Overview', 'Injection', 'Mold', 'Heating', 'Components'], panels: [['Injection', ['Injection pressure', 'Screw speed', 'Injection time', 'Back pressure']], ['Mold', ['Mold temperature', 'Clamp force', 'Mold position', 'Cycle time']], ['Heating', ['Zone 1', 'Zone 2', 'Zone 3', 'Zone 4']]] },
  packaging_machine: { subtitle: 'Automated packaging line equipment', tabs: ['Overview', 'Line', 'Packaging', 'Components', 'Health'], panels: [['Line', ['Line speed', 'Throughput', 'Cycle time', 'Utilization']], ['Packaging', ['Feed', 'Seal', 'Cut', 'Reject rate']], ['Sensors', ['Product detect', 'Jam detect', 'Guard status', 'Counter']]] },
  generator: { subtitle: 'Electrical generation system', tabs: ['Overview', 'Electrical', 'Engine', 'Fuel & Cooling', 'Components'], panels: [['Electrical', ['Output power', 'Voltage', 'Current', 'Frequency']], ['Engine', ['RPM', 'Oil pressure', 'Oil temperature', 'Load']], ['Fuel & cooling', ['Fuel level', 'Coolant temperature', 'Coolant level', 'Air flow']]] },
  transformer: { subtitle: 'Electrical power transformer', tabs: ['Overview', 'Electrical', 'Thermal', 'Protection', 'Components'], panels: [['Electrical', ['Primary voltage', 'Secondary voltage', 'Current', 'Load']], ['Thermal', ['Top-oil temperature', 'Winding temperature', 'Ambient', 'Cooling state']], ['Protection', ['Oil level', 'Pressure relief', 'Buchholz', 'Protection state']]] },
  boiler: { subtitle: 'Steam and thermal process system', tabs: ['Overview', 'Steam', 'Combustion', 'Water', 'Safety'], panels: [['Steam', ['Pressure', 'Temperature', 'Flow', 'Steam quality']], ['Combustion', ['Flame state', 'Fuel flow', 'Air flow', 'Burner load']], ['Water', ['Level', 'Feed flow', 'TDS', 'Water temperature']]] },
  furnace: { subtitle: 'Industrial furnace / oven', tabs: ['Overview', 'Thermal', 'Heating', 'Airflow', 'Safety'], panels: [['Thermal', ['Chamber temperature', 'Setpoint', 'Temperature spread', 'Ramp rate']], ['Heating', ['Heater load', 'Zone 1', 'Zone 2', 'Zone 3']], ['Airflow', ['Flow', 'Pressure', 'Exhaust', 'Fan state']]] },
  hvac: { subtitle: 'Heating, ventilation and air-conditioning system', tabs: ['Overview', 'Cooling', 'Airflow', 'Refrigeration', 'Components'], panels: [['Cooling / heating', ['Supply temperature', 'Return temperature', 'Setpoint', 'Capacity']], ['Airflow', ['Supply flow', 'Return flow', 'Static pressure', 'Filter status']], ['Refrigeration', ['Suction pressure', 'Discharge pressure', 'Compressor load', 'Refrigerant temperature']]] },
  fan_blower: { subtitle: 'Air movement equipment', tabs: ['Overview', 'Drive', 'Airflow', 'Components', 'Health'], panels: [['Drive', ['RPM', 'Motor current', 'Motor temperature', 'Vibration']], ['Airflow', ['Flow', 'Pressure', 'Damper position', 'Efficiency']]] },
  gearbox: { subtitle: 'Mechanical power transmission system', tabs: ['Overview', 'Gearing', 'Lubrication', 'Components', 'Health'], panels: [['Gearing', ['Input RPM', 'Output RPM', 'Torque', 'Load']], ['Lubrication', ['Oil temperature', 'Oil level', 'Oil pressure', 'Particle level']]] },
  turbine: { subtitle: 'Rotating power-generation / process turbine', tabs: ['Overview', 'Rotor', 'Thermal', 'Lubrication', 'Components'], panels: [['Rotor', ['RPM', 'Vibration', 'Axial position', 'Load']], ['Thermal', ['Inlet temperature', 'Outlet temperature', 'Pressure', 'Efficiency']], ['Lubrication', ['Oil pressure', 'Oil temperature', 'Oil level', 'Filter']]] },
  crane_hoist: { subtitle: 'Material handling and lifting system', tabs: ['Overview', 'Hoist', 'Travel', 'Load & Safety', 'Components'], panels: [['Hoist', ['Load', 'Hoist speed', 'Motor current', 'Brake state']], ['Travel', ['Travel speed', 'Position', 'Motor load', 'Limit switches']], ['Load & safety', ['Capacity', 'Utilization', 'Overload state', 'Emergency stop']]] },
  agv_amr: { subtitle: 'Autonomous mobile material handling system', tabs: ['Overview', 'Navigation', 'Drive', 'Battery', 'Sensors'], panels: [['Navigation', ['Location', 'Route', 'Navigation state', 'Obstacle state']], ['Drive', ['Left motor', 'Right motor', 'Speed', 'Drive load']], ['Battery', ['State of charge', 'Voltage', 'Current', 'Temperature']], ['Sensors', ['LiDAR', 'Camera', 'Proximity', 'Safety scanner']]] },
  water_treatment: { subtitle: 'Water treatment and process system', tabs: ['Overview', 'Water Quality', 'Process', 'Pumps & Filters', 'Components'], panels: [['Water quality', ['pH', 'Turbidity', 'Conductivity', 'Temperature']], ['Process', ['Flow', 'Pressure', 'Tank level', 'Chemical dose']], ['Pumps & filters', ['Pump state', 'Filter differential pressure', 'Flow', 'Backwash state']]] },
  other: { subtitle: 'Custom machine profile', tabs: ['Overview', 'Components', 'Health', 'Readings'], panels: [['Custom equipment', ['Operating state', 'Load', 'Temperature', 'Vibration']], ['Custom signals', ['Signal 1', 'Signal 2', 'Signal 3', 'Signal 4']]] },
}

const SIGNAL_MAP = { temperature: ['Temperature', '°C'], vibration: ['Vibration', 'g'], current: ['Current', 'A'], load: ['Load', '%'], humidity: ['Humidity', '%'], pressure: ['Pressure', 'bar'], rpm: ['RPM', 'rpm'], flow: ['Flow', 'm³/h'], voltage: ['Voltage', 'V'], frequency: ['Frequency', 'Hz'], power: ['Power', 'kW'], torque: ['Torque', 'Nm'] }

const normalize = value => String(value || '').toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '')
const formatValue = (label, readings) => {
  const normalized = normalize(label)
  const candidates = [normalized, normalized.replace(/_/g, ''), String(label).toLowerCase(), normalized.split('_')[0]]
  for (const candidate of candidates) {
    const row = readings.find(r => String(r.reading_type || '').toLowerCase() === candidate)
    if (row) return `${Number(row.value).toFixed(1)} ${row.unit || ''}`.trim()
  }
  const signal = Object.entries(SIGNAL_MAP).find(([key]) => String(label).toLowerCase().includes(key))
  if (signal) {
    const row = readings.find(r => String(r.reading_type || '').toLowerCase() === signal[0].toLowerCase())
    if (row) return `${Number(row.value).toFixed(1)} ${row.unit || signal[1]}`.trim()
  }
  return '—'
}

function MiniCard({ label, value, tone = 'neutral' }) { return <div className={`special-mini special-${tone}`}><div className="special-mini-label">{label}</div><div className="special-mini-value">{value}</div></div> }
function Panel({ title, items, readings }) { return <div className="panel special-panel"><div className="panel-header"><span className="panel-title">{title}</span><span className="special-panel-meta">Machine-specific</span></div><div className="panel-body special-panel-grid">{items.map(item => <MiniCard key={item} label={item} value={formatValue(item, readings)} />)}</div></div> }
function ComponentCard({ component, selected, onClick }) { return <button type="button" className={`special-component ${selected ? 'selected' : ''}`} onClick={onClick}><div><div className="special-component-name">{component.name}</div><div className="special-component-id">Component #{component.id ?? '—'}</div></div><StatusBadge status={component.status || 'healthy'} /></button> }

export default function SpecializedMachineDetail({ machine: initialMachine }) {
  const { id } = useParams()
  const navigate = useNavigate()
  const [machine, setMachine] = useState(initialMachine || null)
  const [components, setComponents] = useState([])
  const [readings, setReadings] = useState([])
  const [maintenance, setMaintenance] = useState([])
  const [intelligence, setIntelligence] = useState(null)
  const [selectedTab, setSelectedTab] = useState('Overview')
  const [selectedComponent, setSelectedComponent] = useState(null)
  const [newComponent, setNewComponent] = useState('')
  const [error, setError] = useState(null)

  const load = async () => {
    try {
      const m = await api.get(`/api/machines/${id}`)
      setMachine(m)
      const [c, r, maint] = await Promise.all([
        api.get(`/api/machines/${id}/components`).catch(() => []),
        api.get(`/api/machines/${id}/readings?limit=50`).catch(() => []),
        api.get(`/api/maintenance?machine_id=${id}&limit=20`).catch(() => []),
      ])
      setComponents(Array.isArray(c) ? c : [])
      setReadings(Array.isArray(r) ? r : [])
      setMaintenance(Array.isArray(maint) ? maint : [])
      try { setIntelligence(await api.get(`/api/analytics/machines/${id}/intelligence`)) } catch { setIntelligence(null) }
    } catch (e) { setError(e.message || 'Unable to load machine.') }
  }

  useEffect(() => { load() }, [id])

  const spec = SPECS[machine?.category] || SPECS.other
  const categoryLabel = CATEGORY_LABELS[machine?.category] || machine?.category || 'Machine'
  const healthTone = Number(machine?.health_score) >= 80 ? 'healthy' : Number(machine?.health_score) >= 50 ? 'warning' : 'critical'
  const recentMaintenance = maintenance.slice(0, 4)
  const selectedReadingSummary = useMemo(() => readings.slice(0, 8), [readings])

  usePageHeader(
    <span style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
      <button className="btn secondary" onClick={() => navigate('/machines')}>← Back</button>
      <span>{machine?.name || 'Machine'}</span>
    </span>,
    machine ? <StatusBadge status={machine.status} /> : null
  )

  const addComponent = async (e) => {
    e.preventDefault()
    if (!newComponent.trim()) return
    await api.post(`/api/machines/${id}/components`, { name: newComponent.trim() })
    setNewComponent('')
    clearApiCache(`/api/machines/${id}`)
    await load()
  }

  if (error) return <ErrorState message={error} />
  if (!machine) return <Loading />

  return <>
    <style>{`
      .special-shell{display:flex;flex-direction:column;gap:14px}.special-hero{border:1px solid var(--border);border-radius:14px;background:linear-gradient(135deg,rgba(59,130,246,.10),rgba(15,23,42,.18));padding:18px}.special-hero-top{display:flex;justify-content:space-between;gap:16px;align-items:flex-start}.special-kicker{font-size:11px;text-transform:uppercase;letter-spacing:.12em;color:var(--text-faint);font-weight:700}.special-title{font-size:24px;font-weight:800;margin-top:5px}.special-subtitle{color:var(--text-dim);font-size:13px;margin-top:5px}.special-stat-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin-top:16px}.special-mini{padding:12px;border:1px solid var(--border);border-radius:11px;background:rgba(15,23,42,.24)}.special-mini-label{font-size:10px;color:var(--text-faint);text-transform:uppercase;letter-spacing:.08em}.special-mini-value{font-size:16px;font-weight:800;margin-top:6px}.special-tabs{display:flex;gap:6px;overflow:auto;padding-bottom:2px}.special-tab{border:1px solid var(--border);background:var(--panel);color:var(--text-dim);border-radius:9px;padding:8px 12px;font-size:12px;font-weight:700;cursor:pointer;white-space:nowrap}.special-tab.active{border-color:var(--accent);color:var(--text);box-shadow:0 0 0 1px rgba(59,130,246,.12)}.special-layout{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.special-panel{min-width:0}.special-panel-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:9px}.special-panel-meta{font-size:10px;color:var(--text-faint)}.special-component-list{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:9px}.special-component{display:flex;align-items:center;justify-content:space-between;gap:10px;text-align:left;width:100%;padding:13px;border:1px solid var(--border);border-radius:11px;background:var(--panel);color:var(--text);cursor:pointer}.special-component:hover,.special-component.selected{border-color:var(--accent)}.special-component-name{font-weight:800;font-size:13px}.special-component-id{font-size:10px;color:var(--text-faint);margin-top:4px}.special-empty{color:var(--text-faint);padding:18px 0}.special-detail{margin-top:12px;padding:14px;border:1px solid var(--accent);border-radius:12px;background:rgba(59,130,246,.05)}.special-list{display:flex;flex-direction:column;gap:8px}.special-row{display:flex;justify-content:space-between;gap:12px;padding:10px 0;border-bottom:1px solid var(--border);font-size:12px}.special-row:last-child{border-bottom:0}.special-row-label{color:var(--text-faint)}@media(max-width:900px){.special-stat-grid,.special-layout,.special-component-list{grid-template-columns:1fr 1fr}}@media(max-width:620px){.special-stat-grid,.special-layout,.special-component-list,.special-panel-grid{grid-template-columns:1fr}.special-title{font-size:20px}}
    `}</style>
    <div className="special-shell">
      <section className="special-hero"><div className="special-hero-top"><div><div className="special-kicker">{categoryLabel}</div><div className="special-title">{machine.name}</div><div className="special-subtitle">{spec.subtitle} · {machine.machine_code} · {machine.location || 'Location not set'}</div></div><StatusBadge status={machine.status} /></div><div className="special-stat-grid"><MiniCard label="Health" value={`${machine.health_score}/100`} tone={healthTone} /><MiniCard label="Operating hours" value={`${Number(machine.operating_hours || 0).toFixed(2)} h`} /><MiniCard label="Criticality" value={machine.criticality || '—'} /><MiniCard label="Components" value={components.length} /></div></section>
      <div className="special-tabs">{spec.tabs.map(tab => <button key={tab} className={`special-tab ${selectedTab === tab ? 'active' : ''}`} onClick={() => setSelectedTab(tab)}>{tab}</button>)}</div>
      {selectedTab === 'Overview' && <><div className="special-layout">{spec.panels.map(([title, items]) => <Panel key={title} title={title} items={items} readings={readings} />)}</div><div className="panel"><div className="panel-header"><span className="panel-title">Machine intelligence</span><span className="special-panel-meta">Predictive layer</span></div><div className="panel-body"><div className="special-panel-grid"><MiniCard label="Risk" value={intelligence?.risk_level || intelligence?.risk || '—'} /><MiniCard label="Trend" value={intelligence?.trend || intelligence?.degradation_trend || '—'} /><MiniCard label="Prediction" value={intelligence?.prediction || intelligence?.forecast || '—'} /><MiniCard label="Latest reading" value={readings[0] ? `${readings[0].reading_type}: ${Number(readings[0].value).toFixed(2)} ${readings[0].unit || ''}` : '—'} /></div></div></div></>}
      {selectedTab !== 'Overview' && selectedTab !== 'Components' && selectedTab !== 'Health' && selectedTab !== 'Readings' && <div className="special-layout">{spec.panels.map(([title, items]) => <Panel key={title} title={title} items={items} readings={readings} />)}<div className="panel"><div className="panel-header"><span className="panel-title">Recorded readings</span></div><div className="panel-body special-list">{selectedReadingSummary.map((r, i) => <div className="special-row" key={r.id || i}><span className="special-row-label">{r.reading_type}</span><strong>{Number(r.value).toFixed(2)} {r.unit || ''}</strong></div>)}{!selectedReadingSummary.length && <div className="special-empty">No readings recorded yet.</div>}</div></div></div>}
      {selectedTab === 'Components' && <div className="panel"><div className="panel-header"><div><span className="panel-title">{categoryLabel} components</span><div className="special-panel-meta">Each component can be inspected individually without changing the parent machine.</div></div><span>{components.length}</span></div><div className="panel-body"><div className="special-component-list">{components.map(c => <ComponentCard key={c.id} component={c} selected={selectedComponent?.id === c.id} onClick={() => setSelectedComponent(c)} />)}</div>{components.length === 0 && <div className="special-empty">No components have been added yet.</div>}{selectedComponent && <div className="special-detail"><div className="panel-title">{selectedComponent.name}</div><div className="special-list" style={{marginTop:8}}><div className="special-row"><span className="special-row-label">Parent machine</span><strong>{machine.name}</strong></div><div className="special-row"><span className="special-row-label">Component ID</span><strong>#{selectedComponent.id ?? '—'}</strong></div><div className="special-row"><span className="special-row-label">Status</span><strong>{selectedComponent.status || 'Healthy'}</strong></div></div></div>}<form onSubmit={addComponent} style={{display:'flex',gap:8,marginTop:14}}><input value={newComponent} onChange={e=>setNewComponent(e.target.value)} placeholder="Add a component, e.g. Joint 1, Spindle, Controller" required /><button className="btn" type="submit">+ Add Component</button></form></div></div>}
      {selectedTab === 'Health' && <div className="special-layout"><Panel title="Health signals" items={['Temperature','Vibration','Current','Load','Humidity']} readings={readings} /><div className="panel"><div className="panel-header"><span className="panel-title">Maintenance readiness</span></div><div className="panel-body special-list">{recentMaintenance.map((m, i) => <div className="special-row" key={m.id || i}><span className="special-row-label">{m.title || m.description || m.maintenance_type || 'Maintenance'}</span><strong>{m.status || m.scheduled_date || '—'}</strong></div>)}{!recentMaintenance.length && <div className="special-empty">No maintenance records found for this machine.</div>}</div></div></div>}
      {selectedTab === 'Readings' && <div className="panel"><div className="panel-header"><span className="panel-title">Machine readings</span></div><div className="panel-body special-list">{readings.map((r, i) => <div className="special-row" key={r.id || i}><span><span className="special-row-label">{r.reading_type}</span>{r.recorded_at ? <span style={{marginLeft:8,color:'var(--text-faint)',fontSize:10}}>{new Date(r.recorded_at).toLocaleString()}</span> : null}</span><strong>{Number(r.value).toFixed(2)} {r.unit || ''}</strong></div>)}{!readings.length && <div className="special-empty">No readings recorded yet.</div>}</div></div>}
    </div>
  </>
}

export { CATEGORY_LABELS }
