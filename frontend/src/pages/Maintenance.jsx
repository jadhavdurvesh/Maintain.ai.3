import { useEffect, useState } from 'react'
import api from '../api/client.js'
import StatusBadge from '../components/StatusBadge.jsx'
import { Loading, ErrorState } from './Dashboard.jsx'
import { usePageHeader } from '../PageHeaderContext.jsx'
import { useAuth } from '../AuthContext.jsx'

export default function Maintenance() {
  const [upcoming, setUpcoming] = useState(null)
  const [records, setRecords] = useState([])
  const [machines, setMachines] = useState([])
  const [error, setError] = useState(null)
  const [showPerformanceForm, setShowPerformanceForm] = useState(false)
  const [performanceMachine, setPerformanceMachine] = useState('')
  const [performance, setPerformance] = useState(null)
  const [performanceBusy, setPerformanceBusy] = useState(false)
  const [performanceError, setPerformanceError] = useState('')
  const [form, setForm] = useState({ machine_id: '', type: 'preventive', description: '', scheduled_date: '' })

  const { user } = useAuth()
  const canAdmin = user?.role === 'admin'
  const canComplete = user?.role === 'admin' || user?.role === 'technician'
  const selectedMachine = machines.find(m => String(m.id) === String(performanceMachine))

  usePageHeader('Maintenance', canAdmin ? <button className="btn" onClick={() => setShowPerformanceForm(true)}>+ Machine Performance Form</button> : null)

  const load = () => {
    setError(null)
    Promise.allSettled([
      api.get('/api/maintenance/due/upcoming'),
      api.get('/api/maintenance?limit=50'),
      api.get('/api/machines'),
    ]).then(([u, r, m]) => {
      const failures = []
      if (u.status === 'fulfilled') setUpcoming(u.value); else failures.push(`upcoming maintenance: ${u.reason?.message || u.reason}`)
      if (r.status === 'fulfilled') setRecords(r.value); else failures.push(`maintenance records: ${r.reason?.message || r.reason}`)
      if (m.status === 'fulfilled') setMachines(m.value); else failures.push(`machines: ${m.reason?.message || m.reason}`)
      if (failures.length === 3) setError(failures.join(' | '))
      else if (failures.length) setError(`Some maintenance data could not be loaded: ${failures.join(' | ')}`)
    })
  }

  useEffect(() => { load() }, [])

  useEffect(() => {
    if (!performanceMachine) { setPerformance(null); return }
    const month = new Date().toISOString().slice(0, 7)
    setPerformanceBusy(true); setPerformanceError('')
    api.get(`/api/machines/${performanceMachine}/performance?month=${month}`)
      .then(setPerformance)
      .catch(e => setPerformanceError(e.message || 'Could not load machine performance data.'))
      .finally(() => setPerformanceBusy(false))
  }, [performanceMachine])

  const schedule = async (e) => {
    e.preventDefault()
    if (!form.machine_id) return alert('Choose a machine')
    await api.post(`/api/maintenance/${form.machine_id}`, {
      type: form.type,
      description: form.description,
      scheduled_date: form.scheduled_date ? new Date(form.scheduled_date).toISOString() : null,
    })
    setForm({ machine_id: '', type: 'preventive', description: '', scheduled_date: '' })
    load()
  }

  const complete = async (id) => {
    await api.post(`/api/maintenance/${id}/complete`)
    load()
  }

  const savePerformance = async (e) => {
    e.preventDefault()
    if (!performanceMachine) return
    setPerformanceBusy(true); setPerformanceError('')
    try {
      const p = performance || {}
      const profile = p.profile || {}
      const monthly = p.monthly || {}
      await api.put(`/api/machines/${performanceMachine}/performance/profile`, {
        started_on: profile.started_on || null,
        rated_capacity: profile.rated_capacity == null || profile.rated_capacity === '' ? null : Number(profile.rated_capacity),
        capacity_unit: profile.capacity_unit || null,
        oee_target: profile.oee_target == null || profile.oee_target === '' ? null : Number(profile.oee_target),
      })
      await api.put(`/api/machines/${performanceMachine}/performance/month`, {
        month: p.month,
        planned_hours: monthly.planned_hours == null || monthly.planned_hours === '' ? null : Number(monthly.planned_hours),
        manual_runtime_hours: monthly.manual_runtime_hours == null || monthly.manual_runtime_hours === '' ? null : Number(monthly.manual_runtime_hours),
        total_units: monthly.total_units == null || monthly.total_units === '' ? null : Number(monthly.total_units),
        good_units: monthly.good_units == null || monthly.good_units === '' ? null : Number(monthly.good_units),
        rejected_units: monthly.rejected_units == null || monthly.rejected_units === '' ? null : Number(monthly.rejected_units),
        ideal_cycle_seconds: monthly.ideal_cycle_seconds == null || monthly.ideal_cycle_seconds === '' ? null : Number(monthly.ideal_cycle_seconds),
      })
      setShowPerformanceForm(false)
      setPerformanceMachine('')
      setFeedback?.(null)
      setPerformance(null)
    } catch (e) {
      setPerformanceError(e.message || 'Could not save machine performance data.')
    } finally { setPerformanceBusy(false) }
  }

  const updateProfile = (field, value) => setPerformance(p => ({ ...p, profile: { ...(p?.profile || {}), [field]: value } }))
  const updateMonth = (field, value) => setPerformance(p => ({ ...p, monthly: { ...(p?.monthly || {}), [field]: value } }))

  if (error) return <ErrorState message={error} />
  if (!upcoming) return <Loading />

  return (
    <>
      {showPerformanceForm && canAdmin && (
        <div role="dialog" aria-modal="true" style={{position:'fixed',inset:0,zIndex:1000,background:'rgba(0,0,0,.68)',display:'flex',alignItems:'center',justifyContent:'center',padding:20}}>
          <div className="panel" style={{width:'min(900px,100%)',maxHeight:'90vh',overflowY:'auto'}}>
            <div className="panel-header">
              <div>
                <span className="panel-title">Machine Performance Data</span>
                <div style={{fontSize:11,color:'var(--text-faint)',marginTop:4}}>Select a machine. Existing telemetry and maintenance history fill the automatic KPIs.</div>
              </div>
              <button className="btn secondary" type="button" onClick={() => {setShowPerformanceForm(false);setPerformanceMachine('')}}>Close</button>
            </div>
            <form className="panel-body" onSubmit={savePerformance}>
              <div className="grid-2">
                <div className="field">
                  <label>Machine</label>
                  <select required value={performanceMachine} onChange={e => setPerformanceMachine(e.target.value)}>
                    <option value="">Select machine…</option>
                    {machines.map(m => <option key={m.id} value={m.id}>{m.name} ({m.machine_code})</option>)}
                  </select>
                </div>
                <div className="field">
                  <label>Month</label>
                  <input type="month" disabled={!performanceMachine} value={performance?.month || new Date().toISOString().slice(0,7)} onChange={e => {
                    if (!performanceMachine) return
                    api.get(`/api/machines/${performanceMachine}/performance?month=${e.target.value}`).then(setPerformance).catch(err => setPerformanceError(err.message))
                  }} />
                </div>
              </div>

              {performanceMachine && performance && (
                <>
                  {performanceError && <div style={{color:'var(--critical)',fontSize:12,marginBottom:10}}>{performanceError}</div>}
                  <div style={{marginTop:14,padding:12,border:'1px solid var(--border)',borderRadius:10,background:'var(--panel-raised)'}}>
                    <div style={{fontSize:11,color:'var(--text-faint)',marginBottom:9}}>MACHINE DETAILS — AUTO-FILLED FROM MACHINE RECORD</div>
                    <div className="grid-3">
                      <div><small>Machine Name</small><div className="mono">{selectedMachine?.name || '—'}</div></div>
                      <div><small>Machine Code</small><div className="mono">{selectedMachine?.machine_code || '—'}</div></div>
                      <div><small>Manufacturer</small><div>{selectedMachine?.manufacturer || '—'}</div></div>
                      <div><small>Model</small><div>{selectedMachine?.model_number || '—'}</div></div>
                      <div><small>Category</small><div>{selectedMachine?.category || '—'}</div></div>
                      <div><small>Location</small><div>{selectedMachine?.location || '—'}</div></div>
                      <div><small>Department</small><div>{selectedMachine?.department || '—'}</div></div>
                    </div>
                  </div>

                  <div className="stat-grid" style={{marginTop:14}}>
                    <div className="stat-tile"><div className="stat-label">MACHINE NAME</div><div className="stat-value" style={{fontSize:16}}>{performance.machine_name}</div></div>
                    <div className="stat-tile"><div className="stat-label">STARTED ON</div><div className="stat-value" style={{fontSize:15}}>{performance.started_on ? new Date(performance.started_on).toLocaleDateString() : 'Not entered'}</div></div>
                    <div className="stat-tile"><div className="stat-label">CURRENT WORKING HRS</div><div className="stat-value">{performance.current_working_hours == null ? '—' : Number(performance.current_working_hours).toFixed(1)} h</div></div>
                    <div className="stat-tile"><div className="stat-label">MTBF</div><div className="stat-value">{performance.mtbf_hours == null ? '—' : Number(performance.mtbf_hours).toFixed(1)+' h'}</div></div>
                    <div className="stat-tile"><div className="stat-label">MTTR</div><div className="stat-value">{performance.mttr_minutes == null ? '—' : Number(performance.mttr_minutes).toFixed(1)+' min'}</div></div>
                    <div className="stat-tile"><div className="stat-label">AVAILABILITY</div><div className="stat-value">{performance.availability_percent == null ? '—' : Number(performance.availability_percent).toFixed(1)+'%'}</div></div>
                    <div className="stat-tile"><div className="stat-label">OEE</div><div className="stat-value">{performance.oee_percent == null ? '—' : Number(performance.oee_percent).toFixed(1)+'%'}</div></div>
                  </div>

                  <div style={{marginTop:16,padding:12,border:'1px solid var(--border)',borderRadius:10,color:'var(--text-dim)',fontSize:12}}>
                    <strong>Automatic:</strong> machine name, current working hours, MTBF, MTTR and telemetry-based runtime are filled from MAINTAIN AI.
                    <br/><strong>Manual:</strong> only performance information that is not already stored or reliably measurable is entered below. Machine identity/details are never re-entered.
                  </div>

                  <div className="grid-2" style={{marginTop:16}}>
                    <div className="field"><label>Started on</label><input type="date" value={performance.profile?.started_on?.slice(0,10) || ''} onChange={e=>updateProfile('started_on', e.target.value || null)} /></div>
                    <div className="field"><label>Rated capacity</label><input type="number" min="0" step="0.01" value={performance.profile?.rated_capacity ?? ''} onChange={e=>updateProfile('rated_capacity',e.target.value)} placeholder="e.g. 120" /></div>
                    <div className="field"><label>Capacity unit</label><input value={performance.profile?.capacity_unit || ''} onChange={e=>updateProfile('capacity_unit',e.target.value)} placeholder="parts/hour" /></div>
                    <div className="field"><label>OEE target %</label><input type="number" min="0" max="100" step="0.1" value={performance.profile?.oee_target ?? ''} onChange={e=>updateProfile('oee_target',e.target.value)} /></div>
                    <div className="field"><label>Planned production hours</label><input type="number" min="0" step="0.1" value={performance.monthly?.planned_hours ?? ''} onChange={e=>updateMonth('planned_hours',e.target.value)} /></div>
                    <div className="field"><label>Manual runtime hours <span style={{color:'var(--text-faint)'}}>(fallback)</span></label><input type="number" min="0" step="0.1" value={performance.monthly?.manual_runtime_hours ?? ''} onChange={e=>updateMonth('manual_runtime_hours',e.target.value)} /></div>
                    <div className="field"><label>Total units produced</label><input type="number" min="0" step="1" value={performance.monthly?.total_units ?? ''} onChange={e=>updateMonth('total_units',e.target.value)} /></div>
                    <div className="field"><label>Good units</label><input type="number" min="0" step="1" value={performance.monthly?.good_units ?? ''} onChange={e=>updateMonth('good_units',e.target.value)} /></div>
                    <div className="field"><label>Rejected units</label><input type="number" min="0" step="1" value={performance.monthly?.rejected_units ?? ''} onChange={e=>updateMonth('rejected_units',e.target.value)} /></div>
                    <div className="field"><label>Ideal cycle time (seconds/unit)</label><input type="number" min="0" step="0.01" value={performance.monthly?.ideal_cycle_seconds ?? ''} onChange={e=>updateMonth('ideal_cycle_seconds',e.target.value)} /></div>
                  </div>

                  <div style={{marginTop:14,padding:12,borderRadius:10,background:'var(--panel-raised)',fontSize:11,color:'var(--text-faint)'}}>
                    OEE is only calculated when availability, production performance and quality inputs are available. The system will show “—” instead of inventing a value.
                  </div>
                  <button className="btn" type="submit" disabled={performanceBusy}>{performanceBusy ? 'Saving…' : 'Save Performance Data'}</button>
                </>
              )}

              {performanceMachine && performanceBusy && !performance && <div className="empty-state">Loading machine data…</div>}
              {performanceMachine && performanceError && !performance && <div className="empty-state">{performanceError}</div>}
            </form>
          </div>
        </div>
      )}

      <div className="panel section-gap">
        <div className="panel-header"><span className="panel-title">Smart Scheduler — Operating-Hours Based</span></div>
        <table>
          <thead><tr><th>Machine</th><th>Hours / Interval</th><th>Remaining</th><th>Status</th></tr></thead>
          <tbody>
            {upcoming.map((u) => (
              <tr key={u.machine_id}>
                <td>{u.name}</td><td className="mono">{u.operating_hours} / {u.interval_hours}</td><td className="mono">{u.hours_remaining}h</td>
                <td>{u.overdue ? <StatusBadge status="critical" /> : u.due_soon ? <StatusBadge status="warning" /> : <StatusBadge status="healthy" />}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="grid-2">
        {canAdmin && <div className="panel">
          <div className="panel-header"><span className="panel-title">Schedule Maintenance</span></div>
          <form className="panel-body" onSubmit={schedule}>
            <div className="field"><label>Machine</label><select required value={form.machine_id} onChange={(e) => setForm({ ...form, machine_id: e.target.value })}><option value="">Select…</option>{machines.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}</select></div>
            <div className="field"><label>Type</label><select value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value })}><option value="preventive">Preventive</option><option value="corrective">Corrective</option><option value="breakdown">Breakdown</option><option value="predictive">Predictive</option></select></div>
            <div className="field"><label>Description</label><textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} placeholder="e.g. Inspect motor bearings" /></div>
            <div className="field"><label>Scheduled date</label><input type="date" value={form.scheduled_date} onChange={(e) => setForm({ ...form, scheduled_date: e.target.value })} /></div>
            <button className="btn" type="submit">Schedule</button>
          </form>
        </div>}

        <div className="panel">
          <div className="panel-header"><span className="panel-title">Maintenance Records</span></div>
          <table><thead><tr><th>Type</th><th>Scheduled</th><th>Status</th><th></th></tr></thead><tbody>
            {records.map((r) => <tr key={r.id}><td>{r.description || r.type}</td><td className="mono">{r.scheduled_date ? new Date(r.scheduled_date).toLocaleDateString() : '—'}</td><td><StatusBadge status={r.status === 'completed' ? 'healthy' : 'warning'} /></td><td>{canComplete && r.status !== 'completed' && <button className="btn secondary" onClick={() => complete(r.id)}>Mark done</button>}</td></tr>)}
            {records.length === 0 && <tr><td colSpan={4} className="empty-state">Nothing scheduled yet.</td></tr>}
          </tbody></table></div>
      </div>
    </>

  )
}
