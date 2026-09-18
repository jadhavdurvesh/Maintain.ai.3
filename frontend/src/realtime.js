import { useEffect, useRef, useState } from 'react'
import { getToken } from './api/client.js'
const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL || ''
const SUPABASE_KEY = import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY || ''
function wsUrl() { return SUPABASE_URL.replace(/^http/, 'ws') + '/realtime/v1/websocket?apikey=' + encodeURIComponent(SUPABASE_KEY) + '&vsn=1.0.0' }
export function useTelemetryStream() {
  const [status, setStatus] = useState(SUPABASE_URL && SUPABASE_KEY ? 'connecting' : 'offline')
  const [lastMessageAt, setLastMessageAt] = useState(null); const socketRef = useRef(null); const retryRef = useRef(0); const timerRef = useRef(null); const heartbeatRef = useRef(null)
  useEffect(() => { if (!SUPABASE_URL || !SUPABASE_KEY) return undefined; let stopped = false
    const cleanup = () => { if (timerRef.current) clearTimeout(timerRef.current); if (heartbeatRef.current) clearInterval(heartbeatRef.current) }
    const schedule = () => { if (stopped || timerRef.current) return; const delay = Math.min(30000, 1000 * (2 ** Math.min(retryRef.current, 5))); retryRef.current += 1; setStatus('reconnecting'); timerRef.current = setTimeout(() => { timerRef.current = null; connect() }, delay) }
    const connect = () => { if (stopped) return; cleanup(); setStatus(retryRef.current ? 'reconnecting' : 'connecting'); let ws; try { ws = new WebSocket(wsUrl()) } catch { schedule(); return }; socketRef.current = ws
      ws.onopen = () => { retryRef.current = 0; setStatus('connected'); const org = localStorage.getItem('maintain-ai-org-id') || 'bootstrap'; const topic = 'realtime:org:' + org + ':telemetry'; ws.send(JSON.stringify([String(Date.now()), '1', topic, 'phx_join', { config: { broadcast: { self: false }, private: true }, access_token: getToken() || '' }])); heartbeatRef.current = setInterval(() => { if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify([String(Date.now()), '2', 'phoenix', 'heartbeat', {}])) }, 30000) }
      ws.onmessage = (event) => { try { const msg = JSON.parse(event.data); if (msg && msg.event === 'broadcast') { const payload = msg.payload && (msg.payload.payload || msg.payload); if (payload) { setLastMessageAt(new Date()); window.dispatchEvent(new CustomEvent('maintain-ai-telemetry', { detail: payload })) } } } catch {} }
      ws.onerror = () => setStatus('offline'); ws.onclose = () => { cleanup(); if (!stopped) schedule() }
    }
    connect(); return () => { stopped = true; cleanup(); if (socketRef.current) socketRef.current.close(1000, 'client closed') }
  }, [])
  return { status, lastMessageAt }
}