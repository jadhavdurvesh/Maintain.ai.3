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

const RUNTIME_STATES = [
  ['running', 'Running'],
  ['idle', 'Idle'],
  ['stopped', 'Stopped'],
  ['maintenance', 'Maintenance'],
  ['fault', 'Fault'],
]

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
  const navigate = useNavigate()
  const { authRequired, user } = useAuth()
  const canManageMachines = !authRequired || user?.role === 'admin'
  const canControlRuntime = !authRequired || user?.role === 'admin' || user?.role === 'technician'

  usePageHeader('Machines & Assets', canManageMachines ? (
    <button className="btn" onClick={() => setShowForm((s) => !s)}>
      {showForm ? 'Cancel' : '+ Add Machine'}
    </button>
  ) : null)

  const load = useCallback(() => {
    setError(null)
    return Promise.all([
      api.get('/api/machines'),
      api.get('/api/machines/runtime'),
    ])
      .then(([result, runtimeResult]) => {
        setMachines(Array.isArray(result) ? result : [])
        const next = {}
        ;(Array.isArray(runtimeResult) ? runtimeResult : []).forEach((item) => { next[item.machine_id] = item })
        setRuntime(next)
      })
      .catch((e) => { setMachines([]); setError(e.message || 'Unable to load machines.') })
  }, [])

  useEffect(() => { load() }, [load])

  useEffect(() => {
    if (!machines) return undefined
    const timer = window.setInterval(() => {
      api.get('/api/machines/runtime')
        .then((items) => {
          const next = {}
          ;(Array.isArray(items) ? items : []).forEach((item) => { next[item.machine_id] = item })
          setRuntime(next)
        })
        .catch(() => {})
    }, 5000)
    return () => window.clearInterval(timer)
  }, [machines])

  const submit = async (e) => {
    e.preventDefault()
    try {
      await api.post('/api/machines', {
        ...form,
        operating_hours: Number(form.operating_hours),
        maintenance_interval_hours: Number(form.maintenance_interval_hours),
      })
      setForm(EMPTY_FORM)
      setShowForm(false)
      await load()
    } catch (err) {
      alert(err.message)
    }
  }

  const setMachineRuntime = async (event, machineId, state) => {
    event.stopPropagation()
    try {
      const next = await api.post(`/api/machines/${machineId}/runtime/${state}`)
      setRuntime((current) => ({ ...current, [machineId]: next }))
    } catch (err) {
      alert(err.message)
    }
  }

  if (!machines && !error) return <Loading />

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
        .runtime-controls{display:flex;gap:5px;align-items:center;flex-wrap:wrap}
        .runtime-select{min-width:116px;padding:6px 8px;border-radius:7px;background:var(--panel-bg,#0b1624);color:inherit;border:1px solid rgba(148,163,184,.25)}
      `}</style>

      {error && (
        <div className="panel section-gap">
          <div className="panel-body">
            <ErrorState message={error} />
            <button className="btn secondary" onClick={load} style={{ marginTop: 12 }}>Retry</button>
          </div>
        </div>
      )}

      {showForm && canManageMachines && (
        <div className="panel section-gap">
          <div className="panel-header"><span className="panel-title">New Machine</span></div>
          <form className="panel-body" onSubmit={submit}>
            <div className="grid-3">
              <div className="field"><label>Machine code</label><input required value={form.machine_code} onChange={(e) => setForm({ ...form, machine_code: e.target.value })} placeholder="M-005" /></div>
              <div className="field"><label>Name</label><input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Induction Motor M-005" /></div>
              <div className="field"><label>Category</label><select value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}><option value="induction_motor">Induction motor</option><option value="pump">Pump</option><option value="conveyor">Conveyor</option><option value="compressor">Compressor</option><option value="other">Other</option></select></div>
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
          <thead><tr><th>Code</th><th>Name</th><th>Location</th><th>Operating hours</th><th>Runtime</th><th>Health</th><th>Status</th>{canControlRuntime && <th>Control</th>}</tr></thead>
          <tbody>
            {machines?.map((m) => {
              const live = runtime[m.id]
              return (
                <tr key={m.id} className="clickable" onClick={() => navigate(`/machines/${m.id}`)}>
                  <td className="mono">{m.machine_code}</td>
                  <td title={m.name}>{m.name}</td>
                  <td>{m.location || '—'}</td>
                  <td className="mono runtime-hours">{live ? Number(live.operating_hours).toFixed(2) : Number(m.operating_hours || 0).toFixed(2)} h</td>
                  <td><RuntimeBadge state={live?.state || 'stopped'} /></td>
                  <td className="mono">{m.health_score}/100</td>
                  <td><StatusBadge status={m.status} /></td>
                  {canControlRuntime && (
                    <td onClick={(e) => e.stopPropagation()}>
                      <div className="runtime-controls">
                        <select className="runtime-select" value={live?.state || 'stopped'} onChange={(e) => setMachineRuntime(e, m.id, e.target.value)} aria-label={`Runtime state for ${m.name}`}>
                          {RUNTIME_STATES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                        </select>
                      </div>
                    </td>
                  )}
                </tr>
              )
            })}
            {machines?.length === 0 && !error && <tr><td colSpan={canControlRuntime ? 8 : 7} className="empty-state">No machines are visible for this organization or technician assignment.</td></tr>}
          </tbody>
        </table>
      </div>
    </>
  )
}
