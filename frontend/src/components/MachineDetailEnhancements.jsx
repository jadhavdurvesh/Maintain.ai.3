import { useMemo } from 'react'
import { useDemoMode } from './DemoMode.jsx'

const MOCK_TELEMETRY = [
  ['Temperature', '72.4', '°C'], ['Vibration', '1.18', 'g'], ['Current', '18.6', 'A'], ['Load', '64', '%'], ['Humidity', '58', '%'],
]

function scoreLabel(score) {
  if (score == null) return 'No signal yet'
  if (score >= 0.8) return 'Critical evidence'
  if (score >= 0.6) return 'High evidence'
  if (score >= 0.35) return 'Watch'
  return 'Normal'
}

export default function MachineDetailEnhancements({ machine, components, readings, maintenance, intelligence, liveReadings }) {
  const demoMode = useDemoMode()
  const behaviour = intelligence?.online_behaviour
  const pretrained = intelligence?.pretrained_anomaly
  const latestReading = readings?.[0]
  const activeSignals = behaviour?.multi_sensor?.active_signals ?? 0
  const behaviourScore = behaviour?.behaviour_anomaly_score
  const forecastAvailable = Boolean(pretrained?.available)
  const telemetryFreshness = latestReading?.recorded_at ? new Date(latestReading.recorded_at) : null
  const maintenanceOpen = useMemo(() => (maintenance || []).filter((m) => m.status !== 'completed'), [maintenance])
  const daysToMaintenance = machine?.next_maintenance_date
    ? Math.ceil((new Date(machine.next_maintenance_date).getTime() - Date.now()) / 86400000)
    : null

  return <>
    {demoMode && <div className="panel section-gap" style={{ border: '1px solid rgba(70,230,190,.35)', background: 'linear-gradient(135deg, rgba(70,230,190,.08), rgba(90,150,255,.05))' }}>
      <div className="panel-header"><div><span className="panel-title">Demo Mode · Safe UI Walkthrough</span><div style={{ marginTop: 4, color: 'var(--text-faint)', fontSize: 11 }}>Sample values are generated in the browser only. No machine, telemetry, safety, or inventory records are written.</div></div><span className="badge healthy">UI only</span></div>
      <div className="panel-body" style={{ display: 'grid', gridTemplateColumns: 'repeat(5, minmax(0, 1fr))', gap: 10 }}>
        {MOCK_TELEMETRY.map(([label, value, unit]) => <div key={label} style={{ padding: 12, borderRadius: 10, background: 'rgba(10,20,32,.5)', border: '1px solid var(--border)' }}><div style={{ color: 'var(--text-faint)', fontSize: 11 }}>{label}</div><div className="mono" style={{ fontSize: 22, fontWeight: 700, marginTop: 5 }}>{value}<span style={{ fontSize: 11, marginLeft: 4, color: 'var(--text-dim)' }}>{unit}</span></div></div>)}
      </div>
    </div>}

    <div className="panel section-gap">
      <div className="panel-header"><div><span className="panel-title">Machine Snapshot</span><div style={{ marginTop: 4, color: 'var(--text-faint)', fontSize: 11 }}>Operational context, maintenance readiness and learned evidence in one view</div></div><span className="badge neutral">{machine?.machine_code || `M-${machine?.id}`}</span></div>
      <div className="panel-body">
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, minmax(0, 1fr))', gap: 10 }}>
          <Snapshot label="Category" value={machine?.category || '—'} /><Snapshot label="Manufacturer / Model" value={[machine?.manufacturer, machine?.model_number].filter(Boolean).join(' · ') || '—'} /><Snapshot label="Location / Department" value={[machine?.location, machine?.department].filter(Boolean).join(' · ') || '—'} /><Snapshot label="Maintenance interval" value={`${machine?.maintenance_interval_hours ?? '—'} h`} />
        </div>
        <div style={{ marginTop: 10, display: 'grid', gridTemplateColumns: 'repeat(4, minmax(0, 1fr))', gap: 10 }}>
          <Snapshot label="Last maintenance" value={machine?.last_maintenance_date ? new Date(machine.last_maintenance_date).toLocaleDateString() : '—'} /><Snapshot label="Next maintenance" value={machine?.next_maintenance_date ? new Date(machine.next_maintenance_date).toLocaleDateString() : 'Not scheduled'} /><Snapshot label="Open maintenance" value={maintenanceOpen.length ? `${maintenanceOpen.length} item${maintenanceOpen.length === 1 ? '' : 's'}` : 'None'} /><Snapshot label="Components" value={`${components?.length || 0} tracked`} />
        </div>
      </div>
    </div>

    <div className="panel section-gap">
      <div className="panel-header"><span className="panel-title">Maintenance Intelligence</span><span className={'badge ' + (behaviourScore == null ? 'neutral' : behaviourScore >= 0.6 ? 'warning' : 'healthy')}>{scoreLabel(behaviourScore)}</span></div>
      <div className="panel-body">
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, minmax(0, 1fr))', gap: 10 }}>
          <Insight label="Behaviour anomaly" value={behaviourScore == null ? '—' : `${Math.round(behaviourScore * 100)}%`} detail={behaviour?.severity || 'Waiting for learned state'} />
          <Insight label="Active signals" value={String(activeSignals)} detail={behaviour?.multi_sensor?.correlated ? 'Multi-sensor correlation detected' : 'No multi-sensor correlation'} />
          <Insight label="Time-series model" value={pretrained?.available ? `${Math.round((pretrained.anomaly_score || 0) * 100)}%` : 'Optional'} detail={pretrained?.available ? 'Pretrained anomaly evidence' : 'Model unavailable / not configured'} />
          <Insight label="Telemetry freshness" value={telemetryFreshness && !Number.isNaN(telemetryFreshness.getTime()) ? `${Math.max(0, Math.round((Date.now() - telemetryFreshness.getTime()) / 60000))} min` : '—'} detail={liveReadings && Object.keys(liveReadings).length ? 'Live stream has data' : 'Using stored history'} />
        </div>
        <div style={{ marginTop: 12, padding: 12, borderRadius: 10, border: '1px solid var(--border)', background: 'var(--panel-2)' }}><div style={{ display: 'flex', justifyContent: 'space-between', gap: 16, alignItems: 'center' }}><div><div style={{ fontWeight: 700 }}>What needs attention next?</div><div style={{ marginTop: 4, color: 'var(--text-dim)', fontSize: 12 }}>{daysToMaintenance != null && daysToMaintenance <= 14 ? `Scheduled maintenance is ${daysToMaintenance <= 0 ? 'due now' : `due in ${daysToMaintenance} day${daysToMaintenance === 1 ? '' : 's'}`}.` : activeSignals > 0 ? `${activeSignals} learned signal${activeSignals === 1 ? '' : 's'} currently show elevated behavioural evidence.` : forecastAvailable ? 'No immediate learned anomaly is active; continue watching the available time-series evidence.' : 'No immediate learned anomaly is active. Keep telemetry flowing to strengthen the machine baseline.'}</div></div><div className="mono" style={{ fontSize: 12, color: 'var(--text-faint)' }}>{machine?.operating_hours ?? 0} h runtime</div></div></div>
      </div>
    </div>
  </>
}

function Snapshot({ label, value }) { return <div style={{ padding: 12, borderRadius: 10, background: 'var(--panel-2)', border: '1px solid var(--border)', minHeight: 64 }}><div style={{ color: 'var(--text-faint)', fontSize: 10, textTransform: 'uppercase', letterSpacing: '.05em' }}>{label}</div><div style={{ marginTop: 6, fontSize: 13, fontWeight: 600, lineHeight: 1.35 }}>{value}</div></div> }
function Insight({ label, value, detail }) { return <div style={{ padding: 12, borderRadius: 10, background: 'var(--panel-2)', border: '1px solid var(--border)' }}><div style={{ color: 'var(--text-faint)', fontSize: 10, textTransform: 'uppercase', letterSpacing: '.05em' }}>{label}</div><div className="mono" style={{ marginTop: 6, fontSize: 22, fontWeight: 700 }}>{value}</div><div style={{ marginTop: 4, color: 'var(--text-dim)', fontSize: 11 }}>{detail}</div></div> }
