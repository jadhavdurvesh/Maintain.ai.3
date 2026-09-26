import { useEffect, useState } from 'react'

const STORAGE_KEY = 'maintain-ai-demo-mode'
const EVENT_NAME = 'maintain-ai-demo-mode'

function readEnabled() {
  try { return window.localStorage.getItem(STORAGE_KEY) === 'true' } catch { return false }
}

export function useDemoMode() {
  const [enabled, setEnabled] = useState(readEnabled)
  useEffect(() => {
    const sync = () => setEnabled(readEnabled())
    window.addEventListener(EVENT_NAME, sync)
    window.addEventListener('storage', sync)
    return () => { window.removeEventListener(EVENT_NAME, sync); window.removeEventListener('storage', sync) }
  }, [])
  return enabled
}

export default function DemoModeToggle() {
  const enabled = useDemoMode()
  const toggle = () => {
    const next = !enabled
    try { window.localStorage.setItem(STORAGE_KEY, String(next)) } catch {}
    window.dispatchEvent(new CustomEvent(EVENT_NAME))
  }
  return (
    <button
      className="btn secondary"
      onClick={toggle}
      title={enabled ? 'Demo Mode is on. UI-only demo data is allowed; no backend writes are made by Demo Mode.' : 'Turn on Demo Mode for a safe UI-only walkthrough.'}
      style={{ borderColor: enabled ? 'rgba(70, 230, 190, .55)' : undefined, color: enabled ? 'var(--success)' : undefined }}
    >
      {enabled ? '● Demo Mode ON' : 'Demo Mode'}
    </button>
  )
}
