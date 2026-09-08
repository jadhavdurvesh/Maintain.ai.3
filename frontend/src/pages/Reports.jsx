import { useEffect, useState } from 'react'
import api from '../api/client.js'
import { GenericBarChart } from '../components/Charts.jsx'
import { Loading, ErrorState } from './Dashboard.jsx'
import { usePageHeader } from '../PageHeaderContext.jsx'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export default function Reports() {
  const [reliability, setReliability] = useState(null)
  const [failures, setFailures] = useState(null)
  const [modelStatus, setModelStatus] = useState(null)
  const [training, setTraining] = useState(false)
  const [trainResult, setTrainResult] = useState(null)
  const [error, setError] = useState(null)

  usePageHeader('Reports & Analytics', (
    <div className="chip-row">
      <a className="btn secondary" href={`${API_BASE}/api/reports/export/csv`}>CSV</a>
      <a className="btn secondary" href={`${API_BASE}/api/reports/export/excel`}>Excel</a>
      <a className="btn" href={`${API_BASE}/api/reports/export/pdf`}>PDF Report</a>
    </div>
  ))

  const loadModelStatus = () => api.get('/api/analytics/model-status').then(setModelStatus).catch(() => {})

  useEffect(() => {
    Promise.all([api.get('/api/reports/reliability'), api.get('/api/reports/failure-analysis')])
      .then(([r, f]) => { setReliability(r); setFailures(f) })
      .catch((e) => setError(e.message))
    loadModelStatus()
  }, [])

  const retrain = async () => {
    setTraining(true)
    setTrainResult(null)
    try {
      const result = await api.post('/api/analytics/train', {})
      setTrainResult(result)
      loadModelStatus()
    } finally {
      setTraining(false)
    }
  }

  if (error) return <ErrorState message={error} />
  if (!reliability) return <Loading />

  const faultChartData = reliability.map((r) => ({ name: r.name.length > 12 ? r.name.slice(0, 11) + '…' : r.name, faults: r.fault_count }))
  const completionChartData = reliability
    .filter((r) => r.completion_rate != null)
    .map((r) => ({ name: r.name.length > 12 ? r.name.slice(0, 11) + '…' : r.name, rate: r.completion_rate }))
  const causeChartData = failures.most_common_causes.map(([cause, count]) => ({ name: cause.length > 14 ? cause.slice(0, 13) + '…' : cause, count }))

  return (
    <>
      <div className="panel section-gap">
        <div className="panel-header">
          <span className="panel-title">Predictive Model (local, on-device)</span>
          <span className="badge neutral">scikit-learn</span>
        </div>
        <div className="panel-body">
          <p style={{ color: 'var(--text-dim)', fontSize: 13, marginBottom: 12 }}>
            A small RandomForest model (a few tens of KB, no GPU, runs in milliseconds) trained
            entirely on your own machines' accumulated operating hours, fault history, and
            completed maintenance — not a cloud call, not an LLM. Retrain any time after adding
            machines or logging more history; predictions get more meaningful as that history grows.
          </p>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12 }}>
            {modelStatus?.trained ? (
              <span className="badge healthy">Trained on {modelStatus.n_samples} machines · {new Date(modelStatus.trained_at + 'Z').toLocaleString()}</span>
            ) : (
              <span className="badge neutral">Not trained yet</span>
            )}
            <button className="btn" onClick={retrain} disabled={training}>{training ? 'Training…' : 'Retrain Model'}</button>
          </div>
          {trainResult && !trainResult.trained && (
            <p style={{ color: 'var(--warning)', fontSize: 13 }}>{trainResult.reason}</p>
          )}
          {trainResult?.trained && (
            <div>
              <div style={{ color: 'var(--text-faint)', fontSize: 12, marginBottom: 6 }}>
                FEATURE IMPORTANCE (what drives the model's prediction most)
              </div>
              {trainResult.feature_importances.map((f) => (
                <div key={f.feature} style={{ marginBottom: 8 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12.5, marginBottom: 3 }}>
                    <span>{f.feature.replace(/_/g, ' ')}</span>
                    <span className="mono">{Math.round(f.importance * 100)}%</span>
                  </div>
                  <div className="cause-bar-track"><div className="cause-bar-fill" style={{ width: `${f.importance * 100}%` }} /></div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="grid-2 section-gap">
        <div className="panel">
          <div className="panel-header"><span className="panel-title">Faults by Machine</span></div>
          <div className="panel-body"><GenericBarChart data={faultChartData} xKey="name" yKey="faults" tone="critical" /></div>
        </div>
        <div className="panel">
          <div className="panel-header"><span className="panel-title">Maintenance Completion Rate</span></div>
          <div className="panel-body"><GenericBarChart data={completionChartData} xKey="name" yKey="rate" tone="healthy" /></div>
        </div>
      </div>

      <div className="panel section-gap">
        <div className="panel-header"><span className="panel-title">Machine Reliability</span></div>
        <table>
          <thead><tr><th>Machine</th><th>Faults</th><th>Maintenance Total</th><th>Completed</th><th>Completion Rate</th><th>Health</th></tr></thead>
          <tbody>
            {reliability.map((r) => (
              <tr key={r.machine_id}>
                <td>{r.name}</td>
                <td className="mono">{r.fault_count}</td>
                <td className="mono">{r.maintenance_total}</td>
                <td className="mono">{r.maintenance_completed}</td>
                <td className="mono">{r.completion_rate != null ? `${r.completion_rate}%` : '—'}</td>
                <td className="mono">{r.health_score}/100</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="grid-2">
        <div className="panel">
          <div className="panel-header"><span className="panel-title">Failure Analysis</span></div>
          <div className="panel-body">
            {causeChartData.length > 0
              ? <GenericBarChart data={causeChartData} xKey="name" yKey="count" tone="accent" height={180} />
              : <div className="empty-state">No fault causes logged yet.</div>}
          </div>
        </div>
        <div className="panel">
          <div className="panel-header"><span className="panel-title">Failure Causes (table)</span></div>
          <table>
            <thead><tr><th>Cause</th><th>Occurrences</th></tr></thead>
            <tbody>
              {failures.most_common_causes.map(([cause, count]) => (
                <tr key={cause}><td>{cause}</td><td className="mono">{count}</td></tr>
              ))}
              {failures.most_common_causes.length === 0 && <tr><td colSpan={2} className="empty-state">No fault causes logged yet.</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
    </>
  )
}
