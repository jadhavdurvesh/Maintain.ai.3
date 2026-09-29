import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../api/client.js'
import StatusBadge from '../components/StatusBadge.jsx'
import { Loading, ErrorState } from './Dashboard.jsx'
import { usePageHeader } from '../PageHeaderContext.jsx'
import { useAuth } from '../AuthContext.jsx'

const EMPTY_FORM = {
  machine_code: '', name: '', category: 'induction_motor', manufacturer: '',
  model_number: '', location: '', department: '', operating_hours: 0,
  criticality: 'medium', maintenance_interval_hours: 500,
}

const MAIN_CATEGORIES = [
  { value: 'induction_motor', label: 'Induction motor' },
  { value: 'pump', label: 'Pump' },
  { value: 'conveyor', label: 'Conveyor' },
  { value: 'compressor', label: 'Compressor' },
]

const MORE_CATEGORIES = [
  { value: 'cnc', label: 'CNC machine' },
  { value: 'robot', label: 'Robot' },
  { value: 'lathe', label: 'Lathe' },
  { value: 'milling_machine', label: 'Milling machine' },
  { value: 'drill_press', label: 'Drill press' },
  { value: 'grinding_machine', label: 'Grinding machine' },
  { value: 'hydraulic_press', label: 'Hydraulic press' },
  { value: 'injection_molding', label: 'Injection molding machine' },
  { value: 'packaging_machine', label: 'Packaging machine' },
  { value: 'generator', label: 'Generator' },
  { value: 'transformer', label: 'Transformer' },
  { value: 'boiler', label: 'Boiler' },
  { value: 'furnace', label: 'Furnace / oven' },
  { value: 'hvac', label: 'HVAC unit' },
  { value: 'fan_blower', label: 'Fan / blower' },
  { value: 'gearbox', label: 'Gearbox' },
  { value: 'turbine', label: 'Turbine' },
  { value: 'crane_hoist', label: 'Crane / hoist' },
  { value: 'agv_amr', label: 'AGV / AMR' },
  { value: 'water_treatment', label: 'Water treatment system' },
  { value: 'other', label: 'Other' },
]

const isMoreCategory = (value) => MORE_CATEGORIES.some((category) => category.value === value)

function RuntimeBadge({ state }) {
  const labels = { running: 'Running', idle: 'Idle', stopped: 'Stopped', maintenance: 'Maintenance', fault: 'Fault' }
  return <span className={`runtime-badge runtime-${state || 'stopped'}`}><span className="runtime-dot" />{labels[state] || 'Stopped'}</span>
}

export default function Machines() {
  const [machines, setMachines] = useState(null)
  const [runtime, setRuntime] = useState({})
  const [error, setError] = useState(null)
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState(EMPTY_FORM)
  const [showMoreCategories, setShowMoreCategories] = useState(false)
  const navigate = useNavigate()
  const { authRequired, user } = useAuth()
  const canManageMachines = !authRequired || user?.role === 'admin'

  usePageHeader('Machines & Assets', canManageMachines ? (
    <button className="btn" onClick={() => setShowForm((s) => !s)}>{showForm ? 'Cancel' : '+ Add Machine'}</button>
  ) : null)

  const refreshRuntime = useCallback(() => {
    return api.get('/api/machines/runtime').then((items) => {
      const next = {}
      ;(Array.isArray(items) ? items : []).forEach((item) => { next[item.machine_id] = item })
      setRuntime(next)
    }).catch(() => {})
  }, [])

  const load = useCallback(() => {
    setError(null)
    return api.get('/api/machines')
      .then((result) => {
        setMachines(Array.isArray(result) ? result : [])
        return refreshRuntime()
      })
      .catch((e) => { setMachines([]); setError(e.message || 'Unable to load machines.') })
  }, [refreshRuntime])

  useEffect(() => { load() }, [load])

  // Runtime is automatic and telemetry-derived. Polling also reconciles a
  // machine to Stopped when its current/load telemetry becomes stale.
  useEffect(() => {
    if (!machines) return undefined
    const timer = window.setInterval(refreshRuntime, 3000)
    return () => window.clearInterval(timer)
  }, [machines, refreshRuntime])

  const submit = async (e) => {
    e.preventDefault()
    try {
      await api.post('/api/machines', {
        ...form,
        operating_hours: Number(form.operating_hours),
        maintenance_interval_hours: Number(form.maintenance_interval_hours),
      })
      setForm(EMPTY_FORM)
      setShowMoreCategories(false)
      setShowForm(false)
      await load()
    } catch (err) {
      alert(err.message)
    }
  }

  const handleMainCategoryChange = (e) => {
    const value = e.target.value
    if (value === '__more__') {
      setShowMoreCategories(true)
      setForm({ ...form, category: '' })
      return
    }
    setShowMoreCategories(false)
    setForm({ ...form, category: value })
  }

  const handleMoreCategoryChange = (e) => {
    setForm({ ...form, category: e.target.value })
  }

  if (!machines && !error) return <Loading />

  const mainCategoryValue = showMoreCategories ? '__more__' : form.category

  return (
    <>
      <style>{`
        .runtime-badge{display:inline-flex;align-items:center;gap:7px;padding:4px 9px;border:1px solid rgba(148,163,184,.24);border-radius:999px;font-size:12px;font-weight:700;white-space:nowrap}
        .runtime-dot{width:7px;height:7px;border-radius:50%;background:#64748b}
        .runtime-running .runtime-dot{background:#34d399;box-shadow:0 0 8px rgba(52,211,153,.7)}
        .runtime-idle .runtime-dot{background:#fbbf24}
        .runtime-maintenance .runtime-dot{background:#60a5fa}
        .runtime-fault .runtime-dot{background:#f87171}
        .runtime-hours{font-variant-numeric:tabular-nums;font-weight:700}
        .runtime-note{font-size:11px;color:var(--text-faint);margin-top:3px}
        .category-more{margin-top:10px}
      `}</style>

      {error && (
        <div className="panel section-gap">
          <div className="panel-body"><ErrorState message={error} /><button className="btn secondary" onClick={load} style={{ marginTop: 12 }}>Retry</button></div>
        </div>
      )}

      {showForm && canManageMachines && (
        <div className="panel section-gap">
          <div className="panel-header"><span className="panel-title">New Machine</span></div>
          <form className="panel-body" onSubmit={submit}>
            <div className="grid-3">
              <div className="field"><label>Machine code</label><input required value={form.machine_code} onChange={(e) => setForm({ ...form, machine_code: e.target.value })} placeholder="M-005" /></div>
              <div className="field"><label>Name</label><input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Induction Motor M-005" /></div>
              <div className="field">
                <label>Category</label>
                <select required value={mainCategoryValue} onChange={handleMainCategoryChange}>
                  {MAIN_CATEGORIES.map((category) => <option key={category.value} value={category.value}>{category.label}</option>)}
                  <option value="__more__">More categories...</option>
                </select>
                {showMoreCategories && (
                  <div className="category-more">
                    <select required value={isMoreCategory(form.category) ? form.category : ''} onChange={handleMoreCategoryChange}>
                      <option value="" disabled>Select more machine category</option>
                      {MORE_CATEGORIES.map((category) => <option key={category.value} value={category.value}>{category.label}</option>)}
                    </select>
                  </div>
                )}
              </div>
              <div className="field"><label>Manufacturer</label><input value={form.manufacturer} onChange={(e) => setForm({ ...form, manufacturer: e.target.value })} /></div>
              <div className="field"><label>Location</label><input value={form.location} onChange={(e) => setForm({ ...form, location: e.target.value })} /></div>
              <div className="field"><label>Department</label><input value={form.department} onChange={(e) => setForm({ ...form, department: e.target.value })} /></div>
              <div className="field"><label>Initial operating hours</label><input type="number" min="0" step="0.01" value={form.operating_hours} onChange={(e) => setForm({ ...form, operating_hours: e.target.value })} /></div>
              <div className="field"><label>Maintenance interval (hours)</label><input type="number" min="0" step="0.01" value={form.maintenance_interval_hours} onChange={(e) => setForm({ ...form, maintenance_interval_hours: e.target.value })} /></div>
              <div className="field"><label>Criticality</label><select value={form.criticality} onChange={(e) => setForm({ ...form, criticality: e.target.value })}><option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option></select></div>
            </div>
            <button className="btn" type="submit">Save Machine</button>
          </form>
        </div>
      )}

      <div className="panel">
        <table>
          <thead><tr><th>Code</th><th>Name</th><th>Location</th><th>Operating hours</th><th>Runtime</th><th>Health</th><th>Condition</th></tr></thead>
          <tbody>
            {machines?.map((m) => {
              const live = runtime[m.id]
              return (
                <tr key={m.id} className="clickable" onClick={() => navigate(`/machines/${m.id}`)}>
                  <td className="mono">{m.machine_code}</td>
                  <td title={m.name}>{m.name}</td>
                  <td>{m.location || '—'}</td>
                  <td className="mono runtime-hours">{live ? Number(live.operating_hours).toFixed(2) : Number(m.operating_hours || 0).toFixed(2)} h</td>
                  <td><RuntimeBadge state={live?.state || 'stopped'} /><div className="runtime-note">Automatic from telemetry</div></td>
                  <td className="mono">{m.health_score}/100</td>
                  <td><StatusBadge status={m.status} /></td>
                </tr>
              )
            })}
            {machines?.length === 0 && !error && <tr><td colSpan={7} className="empty-state">No machines are visible for this organization or technician assignment.</td></tr>}
          </tbody>
        </table>
      </div>
    </>
  )
}
