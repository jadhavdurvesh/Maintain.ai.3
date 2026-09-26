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

export default function Machines() {
  const [machines, setMachines] = useState(null)
  const [error, setError] = useState(null)
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState(EMPTY_FORM)
  const navigate = useNavigate()
  const { authRequired, user } = useAuth()
  const canManageMachines = !authRequired || user?.role === 'admin'

  usePageHeader('Machines & Assets', canManageMachines ? (
    <button className="btn" onClick={() => setShowForm((s) => !s)}>
      {showForm ? 'Cancel' : '+ Add Machine'}
    </button>
  ) : null)

  const load = useCallback(() => {
    setError(null)
    return api.get('/api/machines')
      .then((result) => setMachines(Array.isArray(result) ? result : []))
      .catch((e) => { setMachines([]); setError(e.message || 'Unable to load machines.') })
  }, [])

  useEffect(() => { load() }, [load])

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

  if (!machines && !error) return <Loading />

  return (
    <>
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
              <div className="field"><label>Operating hours</label><input type="number" value={form.operating_hours} onChange={(e) => setForm({ ...form, operating_hours: e.target.value })} /></div>
              <div className="field"><label>Maintenance interval (hours)</label><input type="number" value={form.maintenance_interval_hours} onChange={(e) => setForm({ ...form, maintenance_interval_hours: e.target.value })} /></div>
              <div className="field"><label>Criticality</label><select value={form.criticality} onChange={(e) => setForm({ ...form, criticality: e.target.value })}><option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option></select></div>
            </div>
            <button className="btn" type="submit">Save Machine</button>
          </form>
        </div>
      )}

      <div className="panel">
        <table>
          <thead><tr><th>Code</th><th>Name</th><th>Location</th><th>Hours</th><th>Health</th><th>Status</th></tr></thead>
          <tbody>
            {machines?.map((m) => (
              <tr key={m.id} className="clickable" onClick={() => navigate(`/machines/${m.id}`)}>
                <td className="mono">{m.machine_code}</td>
                <td title={m.name}>{m.name}</td>
                <td>{m.location || '—'}</td>
                <td className="mono">{m.operating_hours}</td>
                <td className="mono">{m.health_score}/100</td>
                <td><StatusBadge status={m.status} /></td>
              </tr>
            ))}
            {machines?.length === 0 && !error && <tr><td colSpan={6} className="empty-state">No machines are visible for this organization or technician assignment.</td></tr>}
          </tbody>
        </table>
      </div>
    </>
  )
}
