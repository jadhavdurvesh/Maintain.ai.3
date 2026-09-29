import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import api from '../api/client.js'
import { Loading, ErrorState } from '../pages/Dashboard.jsx'
import MachineDetail from '../pages/MachineDetail.jsx'
import SpecializedMachineDetail from './SpecializedMachineDetail.jsx'

// Legacy categories intentionally stay on the existing machine UI.
// Specialized categories use the engineering-specific component/safety/telemetry UI.
const SPECIALIZED_CATEGORIES = new Set([
  'cnc', 'robot', 'lathe', 'milling_machine', 'drill_press', 'grinding_machine', 'hydraulic_press',
  'injection_molding', 'packaging_machine', 'generator', 'transformer', 'boiler', 'furnace', 'hvac',
  'fan_blower', 'gearbox', 'turbine', 'crane_hoist', 'agv_amr', 'water_treatment', 'other',
])

export default function MachineDetailRouter() {
  const { id } = useParams()
  const [machine, setMachine] = useState(null)
  const [error, setError] = useState(null)
  useEffect(() => {
    let cancelled = false
    setMachine(null); setError(null)
    api.get(`/api/machines/${id}`).then(result => { if (!cancelled) setMachine(result) }).catch(err => { if (!cancelled) setError(err.message || 'Unable to load machine.') })
    return () => { cancelled = true }
  }, [id])
  if (error) return <ErrorState message={error} />
  if (!machine) return <Loading />
  return SPECIALIZED_CATEGORIES.has(machine.category) || String(machine.category || '').startsWith('robot_')
    ? <SpecializedMachineDetail machine={machine} />
    : <MachineDetail />
}
