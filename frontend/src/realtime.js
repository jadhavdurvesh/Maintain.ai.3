import { useEffect, useRef, useState } from 'react'
import api from './api/client.js'

const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL || ''
const SUPABASE_KEY = import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY || ''
const ORG_KEY = 'maintain-ai-org-id'

function wsUrl() {
  return SUPABASE_URL.replace(/^http/, 'ws') +
    '/realtime/v1/websocket?apikey=' + encodeURIComponent(SUPABASE_KEY) +
    '&vsn=1.0.0'
}

function getOrganizationId() {
  const value = localStorage.getItem(ORG_KEY)
  return value && /^\d+$/.test(value) ? value : null
}

export function setRealtimeOrganizationId(organizationId) {
  if (organizationId == null) localStorage.removeItem(ORG_KEY)
  else localStorage.setItem(ORG_KEY, String(organizationId))
  window.dispatchEvent(new CustomEvent('maintain-ai-org-context', {
    detail: organizationId == null ? null : String(organizationId),
  }))
}

export function useTelemetryStream() {
  const [status, setStatus] = useState(SUPABASE_URL && SUPABASE_KEY ? 'waiting-for-org' : 'offline')
  const [lastMessageAt, setLastMessageAt] = useState(null)
  const socketRef = useRef(null)
  const retryRef = useRef(0)
  const timerRef = useRef(null)
  const heartbeatRef = useRef(null)

  useEffect(() => {
    if (!SUPABASE_URL || !SUPABASE_KEY) return undefined

    let stopped = false

    const cleanup = () => {
      if (timerRef.current) clearTimeout(timerRef.current)
      if (heartbeatRef.current) clearInterval(heartbeatRef.current)
      timerRef.current = null
      heartbeatRef.current = null
    }

    const closeSocket = () => {
      cleanup()
      if (socketRef.current) {
        socketRef.current.close(1000, 'organization context changed')
        socketRef.current = null
      }
    }

    const schedule = () => {
      if (stopped || timerRef.current || !getOrganizationId()) return
      const delay = Math.min(30000, 1000 * (2 ** Math.min(retryRef.current, 5)))
      retryRef.current += 1
      setStatus('reconnecting')
      timerRef.current = setTimeout(() => {
        timerRef.current = null
        connect()
      }, delay)
    }

    const connect = () => {
      if (stopped) return
      const org = getOrganizationId()
      if (!org) {
        closeSocket()
        setStatus(org ? 'waiting-for-auth' : 'waiting-for-org')
        window.dispatchEvent(new CustomEvent('maintain-ai-realtime-status', { detail: org ? 'waiting-for-auth' : 'waiting-for-org' }))
        return
      }

      cleanup()
      setStatus(retryRef.current ? 'reconnecting' : 'connecting')
      window.dispatchEvent(new CustomEvent('maintain-ai-realtime-status', { detail: retryRef.current ? 'reconnecting' : 'connecting' }))

      let ws
      try {
        ws = new WebSocket(wsUrl())
      } catch {
        schedule()
        return
      }

      socketRef.current = ws
      ws.onopen = () => {
        const currentOrg = getOrganizationId()
        if (!currentOrg) {
          closeSocket()
          setStatus(currentOrg ? 'waiting-for-auth' : 'waiting-for-org')
          return
        }

        retryRef.current = 0
        setStatus('connected')
        window.dispatchEvent(new CustomEvent('maintain-ai-realtime-status', { detail: 'connected' }))
        const topic = 'realtime:org:' + currentOrg + ':telemetry'
        api.post('/api/auth/realtime-token', {}).then((result) => {
          if (ws.readyState !== WebSocket.OPEN) return
          const realtimeToken = result && result.access_token
          if (!realtimeToken) { ws.close(1008, 'missing realtime token'); return }
          ws.send(JSON.stringify([
          String(Date.now()),
          '1',
          topic,
          'phx_join',
          {
            config: { broadcast: { self: false }, private: true },
            access_token: realtimeToken,
          },
        ]))
        }).catch(() => ws.close(1008, 'realtime authorization failed'))
        heartbeatRef.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify([String(Date.now()), '2', 'phoenix', 'heartbeat', {}]))
          }
        }, 30000)
      }

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data)
          if (msg?.event === 'phx_reply') {
            const reply = msg?.payload?.response
            if (reply?.status === 'error') {
              setStatus('offline')
              window.dispatchEvent(new CustomEvent('maintain-ai-realtime-status', { detail: 'offline' }))
              ws.close(1008, 'realtime channel authorization failed')
            }
            return
          }
          if (msg?.event === 'broadcast') {
            const payload = msg.payload && (msg.payload.payload || msg.payload)
            if (payload?.type === 'telemetry' && payload.machine_id != null) {
              setLastMessageAt(new Date())
              window.dispatchEvent(new CustomEvent('maintain-ai-telemetry', { detail: payload }))
            }
          }
        } catch {}
      }

      ws.onerror = () => { setStatus('offline'); window.dispatchEvent(new CustomEvent('maintain-ai-realtime-status', { detail: 'offline' })) }
      ws.onclose = () => {
        cleanup()
        socketRef.current = null
        if (!stopped) { window.dispatchEvent(new CustomEvent('maintain-ai-realtime-status', { detail: 'reconnecting' })); schedule() }
      }
    }

    const handleOrgContext = () => {
      closeSocket()
      retryRef.current = 0
      connect()
    }

    window.addEventListener('maintain-ai-org-context', handleOrgContext)
    window.addEventListener('maintain-ai-auth-context', handleOrgContext)
    connect()

    return () => {
      stopped = true
      window.removeEventListener('maintain-ai-org-context', handleOrgContext)
      window.removeEventListener('maintain-ai-auth-context', handleOrgContext)
      closeSocket()
    }
  }, [])

  return { status, lastMessageAt }
}
