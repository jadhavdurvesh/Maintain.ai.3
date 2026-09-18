import { useEffect, useRef, useState } from 'react'
import { getToken } from './api/client.js'

function websocketUrl() {
  const base = (typeof window !== 'undefined' && window.maintainAI?.backendUrl?.()) || import.meta.env.VITE_API_URL || window.location.origin
  const url = new URL(base)
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
  url.pathname = '/api/devices/stream'
  url.search = ''
  const token = getToken()
  if (token) url.searchParams.set('token', token)
  return url.toString()
}

export function useTelemetryStream() {
  const [status, setStatus] = useState('connecting')
  const [lastMessageAt, setLastMessageAt] = useState(null)
  const socketRef = useRef(null)
  const retryRef = useRef(0)
  const reconnectTimerRef = useRef(null)
  const heartbeatRef = useRef(null)
  const staleTimerRef = useRef(null)

  useEffect(() => {
    let stopped = false

    const clearTimers = () => {
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current)
      if (heartbeatRef.current) clearInterval(heartbeatRef.current)
      if (staleTimerRef.current) clearTimeout(staleTimerRef.current)
    }

    const scheduleReconnect = () => {
      if (stopped || reconnectTimerRef.current) return
      const delay = Math.min(30000, 1000 * (2 ** Math.min(retryRef.current, 5)))
      retryRef.current += 1
      setStatus('reconnecting')
      reconnectTimerRef.current = setTimeout(() => {
        reconnectTimerRef.current = null
        connect()
      }, delay)
    }

    const connect = () => {
      if (stopped) return
      clearTimers()
      setStatus(retryRef.current ? 'reconnecting' : 'connecting')
      let ws
      try { ws = new WebSocket(websocketUrl()) } catch { scheduleReconnect(); return }
      socketRef.current = ws

      ws.onopen = () => {
        retryRef.current = 0
        setStatus('connected')
        heartbeatRef.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: 'ping' }))
        }, 20000)
      }

      ws.onmessage = (event) => {
        setLastMessageAt(new Date())
        if (staleTimerRef.current) clearTimeout(staleTimerRef.current)
        if (event.data) {
          try { window.dispatchEvent(new CustomEvent('maintain-ai-telemetry', { detail: JSON.parse(event.data) })) } catch { /* ignore malformed events */ }
        }
        staleTimerRef.current = setTimeout(() => {
          if (ws.readyState === WebSocket.OPEN) ws.close(4000, 'stream stale')
        }, 45000)
      }

      ws.onerror = () => setStatus('offline')
      ws.onclose = () => {
        clearTimers()
        if (socketRef.current === ws) socketRef.current = null
        scheduleReconnect()
      }
    }

    connect()
    return () => {
      stopped = true
      clearTimers()
      if (socketRef.current) socketRef.current.close(1000, 'client closed')
    }
  }, [])

  return { status, lastMessageAt }
}
