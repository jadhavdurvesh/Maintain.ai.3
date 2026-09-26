import { Component, useEffect, useState } from 'react'
import { useLocation } from 'react-router-dom'
import api from '../api/client.js'
import MachineDetailEnhancements from './MachineDetailEnhancements.jsx'

function asList(value) {
  if (Array.isArray(value)) return value
  if (Array.isArray(value?.items)) return value.items
  if (Array.isArray(value?.data)) return value.data
  if (Array.isArray(value?.results)) return value.results
  return []
}

function unwrap(value) {
  if (value && typeof value === 'object' && value.data && typeof value.data === 'object' && !Array.isArray(value.data)) return value.data
  return value
}

class EnhancementErrorBoundary extends Component {
  state = { hasError: false }

  static getDerivedStateFromError() {
    return { hasError: true }
  }

  componentDidCatch(error) {
    console.error('Machine detail enhancements failed:', error)
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="panel section-gap">
          <div className="panel-header">
            <span className="panel-title">Machine Intelligence</span>
            <span className="badge neutral">Unavailable</span>
          </div>
          <div className="panel-body">
            <div className="empty-state">Optional machine intelligence could not be displayed. The core machine page remains available.</div>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}

export default function MachineDetailEnhancementsRoute() {
  const { pathname } = useLocation()
  const id = pathname.startsWith('/machines/') ? pathname.split('/')[2]?.split('?')[0] : null
  const [data, setData] = useState(null)
  const [liveReadings, setLiveReadings] = useState({})

  useEffect(() => {
    if (!id || !id.trim()) {
      setData(null)
      return undefined
    }

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
      if (machine.status !== 'fulfilled') {
        setData(null)
        return
      }

      setData({
        machine: unwrap(machine.value),
        components: components.status === 'fulfilled' ? asList(components.value) : [],
        readings: readings.status === 'fulfilled' ? asList(readings.value) : [],
        maintenance: maintenance.status === 'fulfilled' ? asList(maintenance.value) : [],
        intelligence: intelligence.status === 'fulfilled' ? unwrap(intelligence.value) : null,
      })
    }).catch(() => {
      if (!cancelled) setData(null)
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

  return (
    <EnhancementErrorBoundary>
      <MachineDetailEnhancements {...data} liveReadings={liveReadings} />
    </EnhancementErrorBoundary>
  )
}
