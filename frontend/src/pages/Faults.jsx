import { useEffect, useState } from 'react'
import api from '../api/client.js'
import { Loading, ErrorState } from './Dashboard.jsx'
import { usePageHeader } from '../PageHeaderContext.jsx'

const emptyForm = { machine_id: '', description: '', symptoms: '', cause: '', severity: 'warning' }
const severityLabel = { warning: 'Warning', high: 'High', critical: 'Critical', normal: 'Normal' }

export default function Faults() {
  const [faults, setFaults] = useState(null)
  const [machines, setMachines] = useState([])
  const [error, setError] = useState(null)
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState(emptyForm)
  const [filter, setFilter] = useState('all')
  const [busy, setBusy] = useState(false)
  const [toast, setToast] = useState(null)

  usePageHeader('Fault Log', <button className="btn" onClick={() => setShowForm((v) => !v)}>{showForm ? 'Cancel' : '+ Log Fault'}</button>)

  const load = () => Promise.all([api.get('/api/faults'), api.get('/api/machines')])
    .then(([f, m]) => { setFaults(f); setMachines(m) })
    .catch((e) => setError(e.message))

  useEffect(() => { load() }, [])

  useEffect(() => {
    if (!toast) return
    const timer = setTimeout(() => setToast(null), 2600)
    return () => clearTimeout(timer)
  }, [toast])

  const create = async (e) => {
    e.preventDefault()
    if (!form.machine_id || !form.description.trim()) return
    setBusy(true)
    try {
      await api.post('/api/faults', { ...form, machine_id: Number(form.machine_id) })
      setForm(emptyForm); setShowForm(false); await load()
      setToast({ type: 'success', message: 'Fault recorded successfully.' })
    } catch (e) { setToast({ type: 'error', message: `Could not log fault: ${e.message}` }) }
    finally { setBusy(false) }
  }

  const resolve = async (fault) => {
    const resolution = window.prompt('Enter the corrective action / resolution:')
    if (!resolution?.trim()) return
    const cause = window.prompt('Root cause (optional):', fault.cause || '')
    setBusy(true)
    try {
      await api.post(`/api/faults/${fault.id}/resolve`, { resolution: resolution.trim(), cause: cause?.trim() || undefined })
      await load()
      setToast({ type: 'success', message: 'Fault resolved successfully.' })
    } catch (e) { setToast({ type: 'error', message: `Could not resolve fault: ${e.message}` }) }
    finally { setBusy(false) }
  }

  const createWorkOrder = async (fault) => {
    setBusy(true)
    try {
      const priority = fault.severity === 'critical'
        ? 'critical'
        : fault.severity === 'high'
          ? 'high'
          : fault.severity === 'warning'
            ? 'medium'
            : fault.severity === 'normal'
              ? 'low'
              : 'medium'

      await api.post(`/api/faults/${fault.id}/work-order`, {
        machine_id: Number(fault.machine_id),
        problem: fault.description || 'Maintenance issue reported',
        priority,
        recommended_actions: fault.symptoms
          ? `Investigate fault: ${fault.symptoms}`
          : 'Investigate reported fault and confirm root cause.',
      })
      await load()
      setToast({ type: 'success', message: 'Work order created successfully.' })
    } catch (e) { setToast({ type: 'error', message: `Could not create work order: ${e.message}` }) }
    finally { setBusy(false) }
  }

  if (error) return <ErrorState message={error} />
  if (!faults) return <Loading />

  const machineName = (id) => machines.find((m) => m.id === id)?.name || `Machine #${id}`
  const visible = faults.filter((f) => filter === 'all' || (filter === 'open' ? !f.resolved_date : !!f.resolved_date))

  return <>
    {toast && <div className="ui-toast-stack" aria-live="polite"><div className={`ui-toast ${toast.type}`}>{toast.message}</div></div>}
    {showForm && <div className="panel section-gap">
      <form className="panel-body grid-2" onSubmit={create}>
        <div className="field"><label>Machine</label><select required value={form.machine_id} onChange={(e) => setForm({ ...form, machine_id: e.target.value })}><option value="">Select machine…</option>{machines.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}</select></div>
        <div className="field"><label>Severity</label><select value={form.severity} onChange={(e) => setForm({ ...form, severity: e.target.value })}><option value="normal">Normal</option><option value="warning">Warning</option><option value="high">High</option><option value="critical">Critical</option></select></div>
        <div className="field"><label>Fault / problem</label><input required value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} placeholder="Excessive vibration" /></div>
        <div className="field"><label>Suspected cause <span className="text-faint">(optional)</span></label><input value={form.cause} onChange={(e) => setForm({ ...form, cause: e.target.value })} placeholder="Bearing wear / Unknown" /></div>
        <div className="field" style={{ gridColumn: 'span 2' }}><label>Symptoms / observations</label><textarea value={form.symptoms} onChange={(e) => setForm({ ...form, symptoms: e.target.value })} placeholder="Abnormal noise, vibration increased under load…" /></div>
        <button className="btn" type="submit" disabled={busy} style={{ gridColumn: 'span 2' }}>{busy ? 'Saving…' : 'Record Fault'}</button>
      </form>
    </div>}

    <div className="chip-row section-gap">
      {['all', 'open', 'resolved'].map((value) => <button key={value} className={`btn ${filter === value ? '' : 'secondary'}`} onClick={() => setFilter(value)}>{value[0].toUpperCase() + value.slice(1)}</button>)}
      <span className="text-faint" style={{ marginLeft: 6 }}>{visible.length} record{visible.length === 1 ? '' : 's'}</span>
    </div>

    <div className="panel">
      <div className="panel-header"><span className="panel-title">Fault History</span><span className="badge neutral">Persistent records</span></div>
      <div className="panel-body" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {visible.map((f) => <div key={f.id} className="panel" style={{ padding: 14 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'start' }}>
            <div>
              <div style={{ fontSize: 12, color: 'var(--text-faint)', marginBottom: 5 }}>FAULT #{f.id} · {machineName(f.machine_id)}</div>
              <div style={{ fontWeight: 650, marginBottom: 6 }}>{f.description}</div>
              {f.symptoms && <div style={{ fontSize: 13, color: 'var(--text-dim)', marginBottom: 4 }}><b>Symptoms:</b> {f.symptoms}</div>}
              {f.cause && <div style={{ fontSize: 13, color: 'var(--text-dim)', marginBottom: 4 }}><b>Cause:</b> {f.cause}</div>}
              {f.resolution && <div style={{ fontSize: 13, color: 'var(--text-dim)' }}><b>Resolution:</b> {f.resolution}</div>}
            </div>
            <span className={`badge ${f.resolved_date ? 'healthy' : f.severity === 'critical' ? 'critical' : f.severity === 'high' ? 'warning' : 'neutral'}`}>{f.resolved_date ? 'Resolved' : severityLabel[f.severity] || f.severity}</span>
          </div>
          <div className="chip-row" style={{ marginTop: 12 }}>
            {!f.resolved_date && <button className="btn secondary" disabled={busy} onClick={() => resolve(f)}>Resolve</button>}
            {!f.resolved_date && <button className="btn secondary" disabled={busy} onClick={() => createWorkOrder(f)}>Create Work Order</button>}
            <span className="text-faint" style={{ fontSize: 11 }}>{new Date(f.reported_date + 'Z').toLocaleString()}{f.resolved_date ? ` · resolved ${new Date(f.resolved_date + 'Z').toLocaleString()}` : ''}</span>
          </div>
        </div>)}
        {visible.length === 0 && <div className="empty-state">No faults in this view.</div>}
      </div>
    </div>
  </>
}
