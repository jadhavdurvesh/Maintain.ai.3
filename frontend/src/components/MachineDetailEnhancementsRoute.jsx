import { useEffect, useState } from 'react'
import { useLocation } from 'react-router-dom'
import api from '../api/client.js'
import MachineDetailEnhancements from './MachineDetailEnhancements.jsx'

export default function MachineDetailEnhancementsRoute() {
  const { pathname } = useLocation()
  const id = pathname.startsWith('/machines/') ? pathname.split('/')[2] : null
  const [data, setData] = useState(null)
  const [liveReadings, setLiveReadings] = useState({})

  useEffect(() => {
    if (!id || !id.trim()) { setData(null); return }
    let cancelled = false
    setData(null)
    Promise.allSettled([
      api.get(`/api/machines/${id}`),
      api.get(`/api/machines/${id}/components`),
      api.get(`/api/machines/${id}/readings?limit=20`),
      api.get(`/api/maintenance?machine_id=${id}&limit=50`),
      api.get(`/api/analytics/machines/${id}/intelligence`),
    ]).then((results) => {
      if (cancelled) return
      const [machine, components, readings, maintenance, intelligence] = results
      if (machine.status !== 'fulfilled') return
      setData({ machine: machine.value, components: components.status === 'fulfilled' ? components.value : [], readings: readings.status === 'fulfilled' ? readings.value : [], maintenance: maintenance.status === 'fulfilled' ? maintenance.value : [], intelligence: intelligence.status === 'fulfilled' ? intelligence.value : null })
    })
    return () => { cancelled = true }
  }, [id])

  useEffect(() => {
    const handle = (event) => {
      const message = event?.detail
      if (!message || String(message.machine_id) !== String(id) || message.type !== 'telemetry') return
      setLiveReadings((prev) => ({ ...prev, [message.reading_type]: message }))
    }
    window.addEventListener('maintain-ai-telemetry', handle)
    return () => window.removeEventListener('maintain-ai-telemetry', handle)
  }, [id])

  if (!id || !data) return null
  return <MachineDetailEnhancements {...data} liveReadings={liveReadings} />
}
