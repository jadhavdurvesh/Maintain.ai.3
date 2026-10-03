import { useEffect, useState } from 'react'
import api from '../api/client.js'
import StatusBadge from '../components/StatusBadge.jsx'
import { Loading, ErrorState } from './Dashboard.jsx'
import { usePageHeader } from '../PageHeaderContext.jsx'

const PAGE_SIZE = 25

export default function Alerts() {
  usePageHeader('Alerts')
  const [alerts, setAlerts] = useState([])
  const [offset, setOffset] = useState(0)
  const [hasMore, setHasMore] = useState(false)
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState(null)

  const load = async (nextOffset = 0) => {
    const append = nextOffset > 0
    append ? setLoadingMore(true) : setLoading(true)
    setError(null)
    try {
      const batch = await api.get(`/api/alerts?limit=${PAGE_SIZE}&offset=${nextOffset}`)
      const rows = Array.isArray(batch) ? batch : []
      setAlerts(current => append ? [...current, ...rows] : rows)
      setOffset(nextOffset + rows.length)
      setHasMore(rows.length === PAGE_SIZE)
    } catch (e) {
      setError(e.message)
    } finally {
      append ? setLoadingMore(false) : setLoading(false)
    }
  }

  useEffect(() => { load(0) }, [])

  const ack = async (id) => { await api.post(`/api/alerts/${id}/acknowledge`); load(0) }
  const resolve = async (id) => { await api.post(`/api/alerts/${id}/resolve`); load(0) }

  if (error && !alerts.length) return <ErrorState message={error} />
  if (loading) return <Loading />

  return (
    <div className="panel">
      {error && <div className="panel-body" style={{ color: 'var(--danger)' }}>{error}</div>}
      <table>
        <thead><tr><th>Severity</th><th>Message</th><th>Acknowledged</th><th></th></tr></thead>
        <tbody>
          {alerts.map((a) => (
            <tr key={a.id}>
              <td><StatusBadge status={a.severity} /></td>
              <td>{a.message}</td>
              <td>{a.acknowledged ? 'Yes' : '—'}</td>
              <td className="chip-row">
                {!a.acknowledged && <button className="btn secondary" onClick={() => ack(a.id)}>Acknowledge</button>}
                <button className="btn secondary" onClick={() => resolve(a.id)}>Resolve</button>
              </td>
            </tr>
          ))}
          {alerts.length === 0 && <tr><td colSpan={4} className="empty-state">No active alerts. All clear.</td></tr>}
        </tbody>
      </table>
      {hasMore && (
        <div className="panel-body" style={{ textAlign: 'center', borderTop: '1px solid var(--border)' }}>
          <button className="btn secondary" onClick={() => load(offset)} disabled={loadingMore}>
            {loadingMore ? 'Loading more…' : 'Load more alerts'}
          </button>
        </div>
      )}
    </div>
  )
}
