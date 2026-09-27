import { useCallback, useEffect, useRef, useState } from 'react'
import { AlertTriangle, BellRing, CheckCircle2, X } from 'lucide-react'
import api from '../api/client.js'

const POLL_MS = 3500
const MAX_VISIBLE = 4
const TOAST_TTL_MS = 9000

function severityMeta(severity) {
  const value = String(severity || '').toLowerCase()
  if (value === 'critical' || value === 'danger') return { label: 'Critical', className: 'critical', icon: AlertTriangle }
  if (value === 'warning' || value === 'warn') return { label: 'Warning', className: 'warning', icon: AlertTriangle }
  return { label: 'Alert', className: 'info', icon: BellRing }
}

function formatTime(value) {
  const date = value ? new Date(value) : new Date()
  if (Number.isNaN(date.getTime())) return 'Just now'
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

export default function AlertToastLayer() {
  const [toasts, setToasts] = useState([])
  const seenRef = useRef(new Set())
  const initializedRef = useRef(false)
  const timersRef = useRef(new Map())

  const dismiss = useCallback((id) => {
    setToasts((current) => current.filter((toast) => toast.id !== id))
    const timer = timersRef.current.get(id)
    if (timer) window.clearTimeout(timer)
    timersRef.current.delete(id)
  }, [])

  const pushToast = useCallback((alert) => {
    const id = String(alert.id)
    const toast = { ...alert, toastId: `${id}-${Date.now()}` }
    setToasts((current) => [toast, ...current.filter((item) => item.id !== alert.id)].slice(0, MAX_VISIBLE))
    const timer = window.setTimeout(() => dismiss(id), TOAST_TTL_MS)
    timersRef.current.set(id, timer)
  }, [dismiss])

  useEffect(() => {
    let stopped = false

    const poll = async () => {
      if (stopped) return
      try {
        const alerts = await api.get('/api/alerts?active_only=true')
        const rows = Array.isArray(alerts) ? alerts : []
        const currentIds = new Set(rows.map((alert) => String(alert.id)))

        if (!initializedRef.current) {
          rows.forEach((alert) => seenRef.current.add(String(alert.id)))
          initializedRef.current = true
          return
        }

        rows.forEach((alert) => {
          const id = String(alert.id)
          if (!seenRef.current.has(id)) {
            seenRef.current.add(id)
            pushToast(alert)
          }
        })

        // Prevent the in-memory set from growing forever while keeping active alerts known.
        if (seenRef.current.size > 500) {
          seenRef.current = new Set([...seenRef.current].filter((id) => currentIds.has(id)))
        }
      } catch {
        // Alerts are additive UI; a temporary API failure must never disrupt the application.
      }
    }

    poll()
    const interval = window.setInterval(poll, POLL_MS)
    return () => {
      stopped = true
      window.clearInterval(interval)
      timersRef.current.forEach((timer) => window.clearTimeout(timer))
      timersRef.current.clear()
    }
  }, [pushToast])

  if (!toasts.length) return null

  return (
    <div className="alert-toast-stack" aria-live="assertive" aria-atomic="false">
      {toasts.map((toast) => {
        const meta = severityMeta(toast.severity)
        const Icon = meta.icon
        return (
          <div key={toast.toastId} className={`alert-toast ${meta.className}`} role="alert">
            <div className="alert-toast-icon"><Icon size={18} /></div>
            <div className="alert-toast-content">
              <div className="alert-toast-heading">
                <span>{meta.label} alert</span>
                <span className="alert-toast-time">{formatTime(toast.created_at)}</span>
              </div>
              <div className="alert-toast-message">{toast.message}</div>
              <div className="alert-toast-actions">
                <button className="alert-toast-link" onClick={() => { window.location.hash = '#/alerts'; dismiss(String(toast.id)) }}>View alerts</button>
                <button className="alert-toast-dismiss" onClick={() => dismiss(String(toast.id))}>Dismiss</button>
              </div>
            </div>
            <button className="alert-toast-close" aria-label="Dismiss alert" onClick={() => dismiss(String(toast.id))}><X size={16} /></button>
          </div>
        )
      })}
    </div>
  )
}
