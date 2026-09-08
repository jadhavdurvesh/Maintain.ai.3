import { useEffect, useState } from 'react'
import api from '../api/client.js'
import { Loading, ErrorState } from './Dashboard.jsx'
import { usePageHeader } from '../PageHeaderContext.jsx'

const ENTITY_FILTERS = [
  { value: '', label: 'All' },
  { value: 'machine', label: 'Machines' },
  { value: 'work_order', label: 'Work Orders' },
  { value: 'maintenance', label: 'Maintenance' },
  { value: 'alert', label: 'Alerts' },
]

const ACTION_TONE = {
  created: 'healthy',
  scheduled: 'neutral',
  completed: 'healthy',
  archived: 'warning',
  restored: 'healthy',
  acknowledged: 'neutral',
  resolved: 'healthy',
}

export default function History() {
  usePageHeader('History')
  const [entries, setEntries] = useState(null)
  const [count, setCount] = useState(null)
  const [filter, setFilter] = useState('')
  const [error, setError] = useState(null)

  const load = () => {
    const query = filter ? `?entity_type=${filter}&limit=200` : '?limit=200'
    Promise.all([api.get(`/api/audit-log${query}`), api.get('/api/audit-log/count')])
      .then(([e, c]) => { setEntries(e); setCount(c.total_events) })
      .catch((e) => setError(e.message))
  }

  useEffect(() => { load() }, [filter])

  if (error) return <ErrorState message={error} />
  if (!entries) return <Loading />

  return (
    <>
      <div className="panel-body" style={{ padding: 0, marginBottom: 14 }}>
        <p style={{ color: 'var(--text-dim)', fontSize: 13, marginBottom: 12 }}>
          Every machine added, every job completed, every alert resolved — permanently recorded here.
          Archiving a machine hides it from active lists but never deletes its history; nothing on
          this page is ever edited or removed by the app itself.
          {count != null && <span className="mono" style={{ color: 'var(--text-faint)' }}> · {count} event{count === 1 ? '' : 's'} on record</span>}
        </p>
        <div className="chip-row">
          {ENTITY_FILTERS.map((f) => (
            <button
              key={f.value}
              className={`btn ${filter === f.value ? '' : 'secondary'}`}
              onClick={() => setFilter(f.value)}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      <div className="panel">
        <table>
          <thead><tr><th>When</th><th>Event</th><th>By</th></tr></thead>
          <tbody>
            {entries.map((e) => (
              <tr key={e.id}>
                <td className="mono" style={{ whiteSpace: 'nowrap', color: 'var(--text-faint)' }}>
                  {new Date(e.created_at + 'Z').toLocaleString()}
                </td>
                <td>
                  <span className={`badge ${ACTION_TONE[e.action] || 'neutral'}`} style={{ marginRight: 8 }}>{e.action}</span>
                  {e.description}
                </td>
                <td>{e.performed_by || '—'}</td>
              </tr>
            ))}
            {entries.length === 0 && <tr><td colSpan={3} className="empty-state">No events yet — actions you take will show up here.</td></tr>}
          </tbody>
        </table>
      </div>
    </>
  )
}
