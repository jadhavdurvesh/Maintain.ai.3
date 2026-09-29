import { useEffect, useRef, useState } from 'react'
import api, { getToken } from './api/client.js'

const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL || ''
const SUPABASE_KEY = import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY || ''
const ORG_KEY = 'maintain-ai-org-id'

function wsUrl() {
  return SUPABASE_URL.replace(/^http/, 'ws') + '/realtime/v1/websocket?apikey=' + encodeURIComponent(SUPABASE_KEY) + '&vsn=1.0.0'
}

function backendWsUrl() {
  const base = import.meta.env.VITE_API_URL || window.location.origin
  const wsBase = base.replace(/^http:/, 'ws:').replace(/^https:/, 'wss:').replace(/\/$/, '')
  const token = getToken()
  return wsBase + '/api/devices/stream' + (token ? '?token=' + encodeURIComponent(token) : '')
}

function getOrganizationId() {
  const value = localStorage.getItem(ORG_KEY)
  return value && /^\d+$/.test(value) ? value : null
}

export function setRealtimeOrganizationId(organizationId) {
  if (organizationId == null) localStorage.removeItem(ORG_KEY)
  else localStorage.setItem(ORG_KEY, String(organizationId))
  window.dispatchEvent(new CustomEvent('maintain-ai-org-context', { detail: organizationId == null ? null : String(organizationId) }))
}

const LIVE_ALIASES = {
  temperature: ['temperature', 'spindle_temperature', 'motor_temperature', 'wheel_temperature', 'oil_temperature', 'winding_temperature', 'barrel_temperature', 'mold_temperature', 'sealing_temperature', 'steam_temperature', 'coolant_temperature'],
  vibration: ['vibration', 'spindle_vibration', 'chuck_vibration'],
  current: ['current'],
  load: ['load', 'spindle_load', 'motor_load', 'pump_load', 'burner_load'],
  humidity: ['humidity'],
}

function liveAlias(readingType) {
  const normalized = String(readingType || '').toLowerCase()
  for (const [alias, types] of Object.entries(LIVE_ALIASES)) if (types.includes(normalized)) return alias
  return null
}

export function useTelemetryStream() {
  const [status, setStatus] = useState(SUPABASE_URL && SUPABASE_KEY ? 'waiting-for-org' : 'offline')
  const [lastMessageAt, setLastMessageAt] = useState(null)
  const socketRef = useRef(null)
  const supabaseSocketRef = useRef(null)
  const retryRef = useRef(0)
  const timerRef = useRef(null)
  const supabaseTimerRef = useRef(null)
  const heartbeatRef = useRef(null)
  const connectedSourcesRef = useRef(new Set())
  const seenReadingIdsRef = useRef(new Map())

  useEffect(() => {
    let stopped = false

    const publishStatus = () => {
      const connected = connectedSourcesRef.current.size > 0
      const next = connected ? 'connected' : (getOrganizationId() ? 'reconnecting' : 'waiting-for-org')
      setStatus(next)
      window.dispatchEvent(new CustomEvent('maintain-ai-realtime-status', { detail: next }))
    }

    const dispatchTelemetry = (payload) => {
      if (!payload || payload.type !== 'telemetry' || payload.machine_id == null) return
      const readingId = payload.reading_id
      if (readingId != null) {
        if (seenReadingIdsRef.current.has(String(readingId))) return
        seenReadingIdsRef.current.set(String(readingId), Date.now())
        if (seenReadingIdsRef.current.size > 500) {
          const first = seenReadingIdsRef.current.keys().next().value
          if (first != null) seenReadingIdsRef.current.delete(first)
        }
      }
      setLastMessageAt(new Date())
      window.dispatchEvent(new CustomEvent('maintain-ai-telemetry', { detail: payload }))
      const alias = liveAlias(payload.reading_type)
      if (alias && alias !== payload.reading_type) {
        window.dispatchEvent(new CustomEvent('maintain-ai-telemetry', { detail: { ...payload, reading_type: alias, source_reading_type: payload.reading_type } }))
      }
    }

    const cleanupTimers = () => {
      if (timerRef.current) clearTimeout(timerRef.current)
      if (supabaseTimerRef.current) clearTimeout(supabaseTimerRef.current)
      if (heartbeatRef.current) clearInterval(heartbeatRef.current)
      timerRef.current = null
      supabaseTimerRef.current = null
      heartbeatRef.current = null
    }

    const closeBackend = () => {
      if (timerRef.current) clearTimeout(timerRef.current)
      timerRef.current = null
      if (socketRef.current) {
        try { socketRef.current.close(1000, 'telemetry client reconnect') } catch {}
        socketRef.current = null
      }
      connectedSourcesRef.current.delete('backend')
      publishStatus()
    }

    const closeSupabase = () => {
      if (supabaseTimerRef.current) clearTimeout(supabaseTimerRef.current)
      supabaseTimerRef.current = null
      if (heartbeatRef.current) clearInterval(heartbeatRef.current)
      heartbeatRef.current = null
      if (supabaseSocketRef.current) {
        try { supabaseSocketRef.current.close(1000, 'telemetry client reconnect') } catch {}
        supabaseSocketRef.current = null
      }
      connectedSourcesRef.current.delete('supabase')
      publishStatus()
    }

    const scheduleBackend = () => {
      if (stopped || timerRef.current) return
      timerRef.current = setTimeout(() => {
        timerRef.current = null
        connectBackend()
      }, 2000)
    }

    const connectBackend = () => {
      if (stopped) return
      const token = getToken()
      if (!token) { connectedSourcesRef.current.delete('backend'); publishStatus(); return }
      if (socketRef.current && socketRef.current.readyState <= WebSocket.OPEN) return
      let ws
      try { ws = new WebSocket(backendWsUrl()) } catch { scheduleBackend(); return }
      socketRef.current = ws
      ws.onopen = () => {
        retryRef.current = 0
        connectedSourcesRef.current.add('backend')
        publishStatus()
      }
      ws.onmessage = event => {
        try {
          const message = JSON.parse(event.data)
          dispatchTelemetry(message)
        } catch {}
      }
      ws.onerror = () => {
        connectedSourcesRef.current.delete('backend')
        publishStatus()
      }
      ws.onclose = () => {
        if (socketRef.current === ws) socketRef.current = null
        connectedSourcesRef.current.delete('backend')
        publishStatus()
        if (!stopped) scheduleBackend()
      }
    }

    const scheduleSupabase = () => {
      if (stopped || supabaseTimerRef.current || !SUPABASE_URL || !SUPABASE_KEY || !getOrganizationId()) return
      const delay = Math.min(30000, 1000 * (2 ** Math.min(retryRef.current, 5)))
      retryRef.current += 1
      supabaseTimerRef.current = setTimeout(() => {
        supabaseTimerRef.current = null
        connectSupabase()
      }, delay)
      publishStatus()
    }

    const connectSupabase = () => {
      if (stopped || !SUPABASE_URL || !SUPABASE_KEY) return
      const org = getOrganizationId()
      if (!org) { closeSupabase(); return }
      if (supabaseSocketRef.current && supabaseSocketRef.current.readyState <= WebSocket.OPEN) return
      let ws
      try { ws = new WebSocket(wsUrl()) } catch { scheduleSupabase(); return }
      supabaseSocketRef.current = ws
      ws.onopen = () => {
        const currentOrg = getOrganizationId()
        if (!currentOrg) { closeSupabase(); return }
        const topic = 'realtime:org:' + currentOrg + ':telemetry'
        api.post('/api/auth/realtime-token', {}).then(result => {
          if (ws.readyState !== WebSocket.OPEN) return
          const realtimeToken = result?.access_token
          if (!realtimeToken) { ws.close(1008, 'missing realtime token'); return }
          ws.send(JSON.stringify([String(Date.now()), '1', topic, 'phx_join', {
            config: { broadcast: { self: false }, private: true },
            access_token: realtimeToken,
          }]))
        }).catch(() => ws.close(1008, 'realtime authorization failed'))
        heartbeatRef.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify([String(Date.now()), '2', 'phoenix', 'heartbeat', {}]))
        }, 30000)
      }
      ws.onmessage = event => {
        try {
          const msg = JSON.parse(event.data)
          if (msg?.event === 'phx_reply') {
            const reply = msg?.payload?.response
            if (reply?.status === 'ok') {
              retryRef.current = 0
              connectedSourcesRef.current.add('supabase')
              publishStatus()
            } else if (reply?.status === 'error') {
              connectedSourcesRef.current.delete('supabase')
              publishStatus()
              ws.close(1008, 'realtime channel authorization failed')
            }
            return
          }
          if (msg?.event === 'broadcast') {
            const payload = msg.payload && (msg.payload.payload || msg.payload)
            dispatchTelemetry(payload)
          }
        } catch {}
      }
      ws.onerror = () => {
        connectedSourcesRef.current.delete('supabase')
        publishStatus()
      }
      ws.onclose = () => {
        if (heartbeatRef.current) clearInterval(heartbeatRef.current)
        heartbeatRef.current = null
        if (supabaseSocketRef.current === ws) supabaseSocketRef.current = null
        connectedSourcesRef.current.delete('supabase')
        publishStatus()
        if (!stopped) scheduleSupabase()
      }
    }

    const connectAll = () => {
      connectBackend()
      connectSupabase()
    }

    const handleContext = () => {
      closeBackend()
      closeSupabase()
      retryRef.current = 0
      if (!stopped) connectAll()
    }

    window.addEventListener('maintain-ai-org-context', handleContext)
    window.addEventListener('maintain-ai-auth-context', handleContext)
    connectAll()

    return () => {
      stopped = true
      window.removeEventListener('maintain-ai-org-context', handleContext)
      window.removeEventListener('maintain-ai-auth-context', handleContext)
      cleanupTimers()
      closeBackend()
      closeSupabase()
    }
  }, [])

  return { status, lastMessageAt }
}
