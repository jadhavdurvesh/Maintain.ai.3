import { useEffect, useState } from 'react'
import api from '../api/client.js'
import { Loading, ErrorState } from './Dashboard.jsx'
import { usePageHeader } from '../PageHeaderContext.jsx'

const COLUMNS = [
  { key: 'pending', label: 'Pending' },
  { key: 'in_progress', label: 'In Progress' },
  { key: 'completed', label: 'Completed' },
]

export default function WorkOrders() {
  const [orders, setOrders] = useState(null)
  const [machines, setMachines] = useState([])
  const [users, setUsers] = useState([])
  const [error, setError] = useState(null)
  const [showForm, setShowForm] = useState(false)
  const [toast, setToast] = useState(null)
  const [form, setForm] = useState({ machine_id: '', problem: '', priority: 'medium', recommended_actions: '', assigned_to: '' })

  usePageHeader('Work Orders', <button className="btn" onClick={() => setShowForm((s) => !s)}>{showForm ? 'Cancel' : '+ New Work Order'}</button>)

  const load = () => Promise.all([api.get('/api/work-orders'), api.get('/api/machines'), api.get('/api/users')])
    .then(([o, m, u]) => { setOrders(o); setMachines(m); setUsers(u) })
    .catch((e) => setError(e.message))

  useEffect(() => { load() }, [])
  useEffect(() => { if (!toast) return; const timer = setTimeout(() => setToast(null), 2600); return () => clearTimeout(timer) }, [toast])

  const create = async (e) => {
    e.preventDefault()
    if (!form.machine_id) return setToast({ type: 'error', message: 'Choose a machine.' })
    try {
      await api.post('/api/work-orders', { ...form, machine_id: Number(form.machine_id), assigned_to: form.assigned_to || null })
      setForm({ machine_id: '', problem: '', priority: 'medium', recommended_actions: '', assigned_to: '' })
      setShowForm(false); await load(); setToast({ type: 'success', message: 'Work order created successfully.' })
    } catch (e) { setToast({ type: 'error', message: `Could not create work order: ${e.message}` }) }
  }

  const advance = async (id, status) => {
    try { await api.patch(`/api/work-orders/${id}`, { status }); await load(); setToast({ type: 'success', message: status === 'completed' ? 'Work order completed.' : 'Work order started.' }) }
    catch (e) { setToast({ type: 'error', message: `Could not update work order: ${e.message}` }) }
  }

  if (error) return <ErrorState message={error} />
  if (!orders) return <Loading />

  const machineName = (id) => machines.find((m) => m.id === id)?.name || `#${id}`
  const assignableUsers = users.filter((u) => u.active !== false && u.role !== 'viewer')

  return (
    <>
      {toast && <div className="ui-toast-stack" aria-live="polite"><div className={`ui-toast ${toast.type}`}>{toast.message}</div></div>}
      {showForm && (
        <div className="panel section-gap">
          <form className="panel-body grid-3" onSubmit={create} style={{ alignItems: 'end' }}>
            <div className="field"><label>Machine</label><select required value={form.machine_id} onChange={(e) => setForm({ ...form, machine_id: e.target.value })}><option value="">Select…</option>{machines.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}</select></div>
            <div className="field"><label>Priority</label><select value={form.priority} onChange={(e) => setForm({ ...form, priority: e.target.value })}><option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option><option value="critical">Critical</option></select></div>
            <div className="field"><label>Assigned to</label><select value={form.assigned_to} onChange={(e) => setForm({ ...form, assigned_to: e.target.value })}><option value="">Unassigned</option>{assignableUsers.map((u) => <option key={u.id} value={u.username}>{u.full_name || u.username} · {u.role}</option>)}</select></div>
            <div className="field" style={{ gridColumn: 'span 2' }}><label>Problem</label><input required value={form.problem} onChange={(e) => setForm({ ...form, problem: e.target.value })} placeholder="High temperature" /></div>
            <div className="field"><label>Recommended actions</label><input value={form.recommended_actions} onChange={(e) => setForm({ ...form, recommended_actions: e.target.value })} placeholder="Inspect cooling, check load" /></div>
            <button className="btn" type="submit" style={{ gridColumn: 'span 3' }}>Create Work Order</button>
          </form>
        </div>
      )}

      <div className="grid-3">
        {COLUMNS.map((col) => {
          const columnOrders = orders.filter((o) => o.status === col.key)
          return <div className="panel" key={col.key}>
            <div className="panel-header"><span className="panel-title">{col.label} ({columnOrders.length})</span></div>
            <div className="panel-body" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {columnOrders.map((o) => (
                <div key={o.id} className="panel" style={{ padding: 12 }}>
                  <div style={{ fontSize: 12, color: 'var(--text-faint)', marginBottom: 4 }}>WORK ORDER #{o.id} · {machineName(o.machine_id)}</div>
                  <div style={{ marginBottom: 7, fontWeight: 600 }}>{o.problem}</div>
                  <div style={{ fontSize: 12, color: 'var(--text-dim)', marginBottom: 9 }}>
                    <span className={`badge ${o.priority === 'critical' ? 'critical' : o.priority === 'high' ? 'warning' : 'neutral'}`}>{o.priority}</span>
                    <span style={{ marginLeft: 8 }}>Assigned: {o.assigned_to || 'Unassigned'}</span>
                  </div>
                  {o.recommended_actions && <div style={{ fontSize: 12, color: 'var(--text-faint)', marginBottom: 9, whiteSpace: 'pre-line' }}>{o.recommended_actions}</div>}
                  <div className="chip-row">
                    {col.key === 'pending' && <button className="btn secondary" onClick={() => advance(o.id, 'in_progress')}>Start</button>}
                    {col.key === 'in_progress' && <button className="btn secondary" onClick={() => advance(o.id, 'completed')}>Complete</button>}
                  </div>
                </div>
              ))}
              {columnOrders.length === 0 && <div className="empty-state">None</div>}
            </div>
          </div>
        })}
      </div>
    </>
  )
}
