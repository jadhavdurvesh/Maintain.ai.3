import { useEffect, useState } from 'react'
import { Sun, Moon } from 'lucide-react'

function getInitialTheme() {
  const stored = localStorage.getItem('maintain-ai-theme')
  if (stored === 'light' || stored === 'dark') return stored
  return 'dark'
}

export function useTheme() {
  const [theme, setTheme] = useState(getInitialTheme)

  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark')
    document.documentElement.classList.toggle('light', theme === 'light')
    localStorage.setItem('maintain-ai-theme', theme)
  }, [theme])

  return [theme, setTheme]
}

/** Escape hatch for hardware where blur isn't hardware-accelerated — falls
 * back to opaque panels instead of backdrop-filter. Off by default since
 * most machines handle blur fine; persisted so it's a one-time choice. */
export function useReducedEffects() {
  const [reduced, setReduced] = useState(() => localStorage.getItem('maintain-ai-reduced-effects') === 'true')

  useEffect(() => {
    document.documentElement.classList.toggle('reduced-effects', reduced)
    localStorage.setItem('maintain-ai-reduced-effects', String(reduced))
  }, [reduced])

  return [reduced, setReduced]
}

export default function ThemeToggle({ theme, setTheme }) {
  const isDark = theme === 'dark'
  return (
    <button
      className="theme-toggle"
      onClick={() => setTheme(isDark ? 'light' : 'dark')}
      aria-label="Toggle light/dark theme"
      title={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
    >
      {isDark ? <Moon size={15} strokeWidth={1.75} /> : <Sun size={15} strokeWidth={1.75} />}
    </button>
  )
}
