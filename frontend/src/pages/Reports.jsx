import { useEffect, useState } from 'react'
import api, { getToken } from '../api/client.js'
import { formatDateTime } from '../utils/dates.js'
import { GenericBarChart } from '../components/Charts.jsx'
import { Loading, ErrorState } from './Dashboard.jsx'
import { usePageHeader } from '../PageHeaderContext.jsx'

const API_BASE = import.meta.env.VITE_API_URL || ''

export default function Reports() {
  const [reliability, setReliability] = useState(null)
  const [failures, setFailures] = useState(null)
  const [modelStatus, setModelStatus] = useState(null)
  const [training, setTraining] = useState(false)
  const [trainResult, setTrainResult] = useState(null)
  const [error, setError] = useState(null)

  const downloadExport = async (format) => {
    try {
      const token = getToken()
      const headers = token
        ? { Authorization: `Bearer ${token}` }
        : {}

      const response = await fetch(
        `${API_BASE}/api/reports/export/${format}`,
        { headers }
      )

      if (!response.ok) {
        const body = await response.text()
        throw new Error(`${response.status} ${response.statusText}: ${body}`)
      }

      const blob = await response.blob()
      const disposition = response.headers.get('content-disposition') || ''
      const match = disposition.match(/filename="?([^\"]+)"?/i)

      const extension =
        format === 'gemini-pdf' ? 'pdf' :
        format === 'all' ? 'zip' :
        format === 'pdf' ? 'pdf' :
        format === 'excel' ? 'xlsx' :
        'csv'

      const filename =
        match?.[1] || `maintain_ai_report.${extension}`

      const url = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = filename
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(url)
    } catch (error) {
      console.error('Export failed:', error)
      alert(`Export failed: ${error.message}`)
    }
  }

  const downloadGeminiPdf = () => downloadExport('gemini-pdf')

  const exportDatasets = [
    ['all', 'Everything (ZIP)'], ['workorders', 'Work Orders'], ['maintenance', 'Maintenance'], ['faults', 'Faults'], ['alerts', 'Alerts'],
    ['sensor_readings', 'Sensor Readings'], ['components', 'Components'], ['machines', 'Machines'], ['safety', 'Safety Settings'],
    ['safety_events', 'Safety Events'], ['spare_parts', 'Spare Parts'], ['notifications', 'Notifications'],
  ]

  const downloadDataset = async (dataset) => {
    if (dataset === 'all') return downloadExport('all')
    try {
      const token = getToken()
      const response = await fetch(`${API_BASE}/api/reports/export/${dataset}.csv`, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
      if (!response.ok) throw new Error(await response.text())
      const blob = await response.blob()
      const disposition = response.headers.get('content-disposition') || ''
      const match = disposition.match(/filename="?([^"]+)"?/i)
      const url = window.URL.createObjectURL(blob)
      const link = document.createElement('a'); link.href = url; link.download = match?.[1] || `maintain_ai_${dataset}.csv`; document.body.appendChild(link); link.click(); link.remove(); window.URL.revokeObjectURL(url)
    } catch (e) { alert(`Export failed: ${e.message}`) }
  }

  usePageHeader('Reports & Analytics', (
    <div className="chip-row">
      <button className="btn secondary" onClick={() => downloadExport('csv')}>Summary CSV</button>
      <button className="btn secondary" onClick={() => downloadExport('excel')}>Excel Report</button>
      <button className="btn" onClick={() => downloadExport('pdf')}>PDF Report</button>
      <button className="btn" onClick={downloadGeminiPdf}>✨ Gemini Detailed PDF</button>
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
          <span className="panel-title">AI Detailed Report</span>
          <span className="badge neutral">Gemini + MAINTAIN AI evidence</span>
        </div>
        <div className="panel-body">
          <p style={{color:'var(--text-dim)',fontSize:13,marginBottom:10}}>
            Generate a detailed PDF combining machine condition, telemetry evidence, faults, maintenance, work orders, alerts and Gemini's evidence-grounded narrative, procedures and possible causes.
          </p>
          <button className="btn" onClick={downloadGeminiPdf}>Generate Gemini Detailed PDF</button>
          <p style={{color:'var(--text-faint)',fontSize:11,marginTop:9}}>Gemini is advisory: the report distinguishes supplied evidence from unconfirmed AI analysis and does not replace technician verification or safety procedures.</p>
        </div>
      </div>

      <div className="panel section-gap">
        <div className="panel-header">
          <span className="panel-title">Export Data</span
          <span className="badge neutral">CSV / ZIP</span>
        </div>
        <div className="panel-body">
          <p style={{ color: 'var(--text-dim)', fontSize: 13, marginBottom: 12 }}>
            Export individual operational datasets or download a complete archive. Historical records are exported; nothing is deleted or changed.
          </p>
          <div className="chip-row">
            {exportDatasets.map(([key, label]) => <button key={key} className={key === 'all' ? 'btn' : 'btn secondary'} onClick={() => downloadDataset(key)}>{label}</button>)}
          </div>
        </div>
      </div>

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
              <span className="badge healthy">Trained on {modelStatus.n_samples} machines · {formatDateTime(modelStatus.trained_at)}</span>
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
