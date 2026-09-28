import { useCallback, useEffect, useRef, useState } from 'react'
import { AlertTriangle, BellRing, X } from 'lucide-react'
import api from '../api/client.js'

const POLL_MS = 3500
const MAX_VISIBLE = 4
const TOAST_TTL_MS = 9000
const NOTIFICATION_PREF_KEY = 'maintain-ai-desktop-alerts'
const DISMISSED_ALERTS_KEY = 'maintain-ai-dismissed-alerts'

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

function readDismissedAlerts() {
  try {
    const raw = sessionStorage.getItem(DISMISSED_ALERTS_KEY)
    const parsed = raw ? JSON.parse(raw) : []
    return new Set(Array.isArray(parsed) ? parsed.map(String) : [])
  } catch {
    return new Set()
  }
}

function writeDismissedAlerts(ids) {
  try {
    sessionStorage.setItem(DISMISSED_ALERTS_KEY, JSON.stringify([...ids].slice(-500)))
  } catch {}
}

function notifyDesktop(alert) {
  if (!('Notification' in window) || Notification.permission !== 'granted') return
  const meta = severityMeta(alert?.severity)
  const notification = new Notification(`MAINTAIN AI — ${meta.label} alert`, {
    body: alert?.message || 'A new maintenance alert requires attention.',
    tag: `maintain-ai-alert-${alert?.id ?? Date.now()}`,
    requireInteraction: meta.label === 'Critical',
    silent: false,
  })
  notification.onclick = () => {
    window.focus()
    window.location.hash = '#/alerts'
    notification.close()
  }
}

export default function AlertToastLayer() {
  const [toasts, setToasts] = useState([])
  const [desktopEnabled, setDesktopEnabled] = useState(() => {
    try { return localStorage.getItem(NOTIFICATION_PREF_KEY) === 'enabled' } catch { return false }
  })
  const seenRef = useRef(new Set())
  const dismissedRef = useRef(readDismissedAlerts())
  const initializedRef = useRef(false)
  const timersRef = useRef(new Map())

  const enableDesktopNotifications = useCallback(async () => {
    if (!('Notification' in window)) return false
    const permission = await Notification.requestPermission()
    const enabled = permission === 'granted'
    setDesktopEnabled(enabled)
    try { localStorage.setItem(NOTIFICATION_PREF_KEY, enabled ? 'enabled' : 'disabled') } catch {}
    return enabled
  }, [])

  const dismiss = useCallback((id) => {
    const normalizedId = String(id)
    dismissedRef.current.add(normalizedId)
    writeDismissedAlerts(dismissedRef.current)
    setToasts((current) => current.filter((toast) => String(toast.id) !== normalizedId))
    const timer = timersRef.current.get(normalizedId)
    if (timer) window.clearTimeout(timer)
    timersRef.current.delete(normalizedId)
  }, [])

  const pushToast = useCallback((alert) => {
    const id = String(alert.id)
    if (dismissedRef.current.has(id)) return
    const toast = { ...alert, toastId: `${id}-${Date.now()}` }
    setToasts((current) => [toast, ...current.filter((item) => String(item.id) !== id)].slice(0, MAX_VISIBLE))
    const previousTimer = timersRef.current.get(id)
    if (previousTimer) window.clearTimeout(previousTimer)
    const timer = window.setTimeout(() => dismiss(id), TOAST_TTL_MS)
    timersRef.current.set(id, timer)
    notifyDesktop(alert)
  }, [dismiss])

  useEffect(() => {
    let stopped = false
    const poll = async () => {
      if (stopped) return
      try {
        const alerts = await api.get('/api/alerts?active_only=true')
        const rows = Array.isArray(alerts) ? alerts : []
        const currentIds = new Set(rows.map((alert) => String(alert.id)))

        // Forget dismissed IDs once the backend alert is no longer active.
        dismissedRef.current = new Set([...dismissedRef.current].filter((id) => currentIds.has(id)))
        writeDismissedAlerts(dismissedRef.current)

        if (!initializedRef.current) {
          rows.forEach((alert) => seenRef.current.add(String(alert.id)))
          initializedRef.current = true
          return
        }

        rows.forEach((alert) => {
          const id = String(alert.id)
          if (!seenRef.current.has(id)) {
            seenRef.current.add(id)
            if (!dismissedRef.current.has(id)) pushToast(alert)
          }
        })

        if (seenRef.current.size > 500) {
          seenRef.current = new Set([...seenRef.current].filter((id) => currentIds.has(id)))
        }
      } catch {}
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

  const supported = 'Notification' in window
  const permission = supported ? Notification.permission : 'unsupported'

  return (
    <>
      {supported && permission !== 'granted' && !desktopEnabled && (
        <button className="desktop-alert-enable" onClick={enableDesktopNotifications} title="Enable desktop notifications for new maintenance alerts">
          <BellRing size={15} /> Enable desktop alerts
        </button>
      )}
      {toasts.length > 0 && (
        <div className="alert-toast-stack" aria-live="assertive" aria-atomic="false">
          {toasts.map((toast) => {
            const meta = severityMeta(toast.severity)
            const Icon = meta.icon
            const id = String(toast.id)
            return (
              <div key={toast.toastId} className={`alert-toast ${meta.className}`} role="alert">
                <div className="alert-toast-icon"><Icon size={18} /></div>
                <div className="alert-toast-content">
                  <div className="alert-toast-heading"><span>{meta.label} alert</span><span className="alert-toast-time">{formatTime(toast.created_at)}</span></div>
                  <div className="alert-toast-message">{toast.message}</div>
                  <div className="alert-toast-actions">
                    <button type="button" className="alert-toast-link" onClick={(event) => { event.stopPropagation(); window.location.hash = '#/alerts'; dismiss(id) }}>View alerts</button>
                    <button type="button" className="alert-toast-dismiss" onClick={(event) => { event.stopPropagation(); dismiss(id) }}>Dismiss</button>
                  </div>
                </div>
                <button type="button" className="alert-toast-close" aria-label="Dismiss alert" onClick={(event) => { event.stopPropagation(); dismiss(id) }}><X size={16} /></button>
              </div>
            )
          })}
        </div>
      )}
    </>
  )
}
