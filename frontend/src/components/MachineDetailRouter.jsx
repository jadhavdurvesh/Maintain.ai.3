import { useEffect, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import api from '../api/client.js'
import { Loading, ErrorState } from '../pages/Dashboard.jsx'
import MachineDetail from '../pages/MachineDetail.jsx'
import SpecializedMachineDetail from './SpecializedMachineDetail.jsx'

const SPECIALIZED = new Set(['cnc','robot','3d_printer','lathe','milling_machine','drill_press','grinding_machine','hydraulic_press','injection_molding','packaging_machine','generator','transformer','boiler','furnace','hvac','fan_blower','gearbox','turbine','crane_hoist','specialized_other'])
const isSpecialized = category => SPECIALIZED.has(String(category || '')) || String(category || '').startsWith('robot_')

function SpecializedTelemetryBridge({ id }) {
  const seen = useRef(new Set())
  const baselineReady = useRef(false)

  useEffect(() => {
    let stopped = false
    let timer = null
    const onRealtime = event => {
      const data = event?.detail
      if (String(data?.machine_id) !== String(id) || data?.type !== 'telemetry' || data?.reading_id == null) return
      seen.current.add(String(data.reading_id))
    }
    const poll = async () => {
      if (stopped) return
      try {
        const result = await api.get(`/api/machines/${id}/readings?limit=40&ts=${Date.now()}`)
        const rows = Array.isArray(result) ? result : []
        if (!baselineReady.current) {
          rows.forEach(row => { if (row?.id != null) seen.current.add(String(row.id)) })
          baselineReady.current = true
        } else {
          const fresh = [...rows].reverse().filter(row => row?.id != null && !seen.current.has(String(row.id)))
          for (const row of fresh) {
            seen.current.add(String(row.id))
            window.dispatchEvent(new CustomEvent('maintain-ai-telemetry', {
              detail: { ...row, machine_id: row.machine_id ?? id, type: 'telemetry' },
            }))
          }
          if (seen.current.size > 500) seen.current = new Set([...seen.current].slice(-250))
        }
      } catch {
        // The realtime channel remains the primary transport; polling is a durable fallback.
      }
      if (!stopped) timer = window.setTimeout(poll, 2000)
    }
    window.addEventListener('maintain-ai-telemetry', onRealtime)
    poll()
    return () => {
      stopped = true
      if (timer) window.clearTimeout(timer)
      window.removeEventListener('maintain-ai-telemetry', onRealtime)
    }
  }, [id])

  return null
}

export default function MachineDetailRouter() {
  const { id } = useParams()
  const [machine, setMachine] = useState(null)
  const [error, setError] = useState(null)
  useEffect(() => {
    let cancelled = false
    setMachine(null)
    setError(null)
    api.get(`/api/machines/${id}`).then(m => { if (!cancelled) setMachine(m) }).catch(e => { if (!cancelled) setError(e.message || 'Unable to load machine') })
    return () => { cancelled = true }
  }, [id])
  if (error) return <ErrorState message={error} />
  if (!machine) return <Loading />
  const specialized = isSpecialized(machine.category)
  return specialized
    ? <><SpecializedTelemetryBridge id={id} /><SpecializedMachineDetail /></>
    : <MachineDetail />
}
