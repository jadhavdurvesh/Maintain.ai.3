const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL || ''
const SUPABASE_KEY = import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY || ''
const STORAGE_KEY = 'maintain-ai-supabase-session'
const enabled = Boolean(SUPABASE_URL && SUPABASE_KEY)
let session = null
let refreshTimer = null
const listeners = new Set()

try { session = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null') } catch {}
try {
  const hash = typeof window !== 'undefined' ? new URLSearchParams(window.location.hash.replace(/^#/, '')) : null
  const accessToken = hash?.get('access_token')
  const refreshToken = hash?.get('refresh_token')
  if (accessToken && refreshToken) {
    session = {
      access_token: accessToken,
      refresh_token: refreshToken,
      expires_in: Number(hash.get('expires_in') || 3600),
      expires_at: Math.floor(Date.now() / 1000) + Number(hash.get('expires_in') || 3600),
      token_type: hash.get('token_type') || 'bearer',
      user: null,
    }
    localStorage.setItem(STORAGE_KEY, JSON.stringify(session))
    if (typeof window !== 'undefined') window.history.replaceState({}, document.title, window.location.pathname + window.location.search)
  }
} catch {}


const emit = () => {
  listeners.forEach(fn => fn(session))
  if (typeof window !== 'undefined') window.dispatchEvent(new CustomEvent('maintain-ai-auth-context', { detail: session ? { access_token: session.access_token || null } : null }))
}

const request = async (path, options = {}) => {
  const res = await fetch(SUPABASE_URL + path, { ...options, headers: { apikey: SUPABASE_KEY, 'Content-Type': 'application/json', ...(options.headers || {}) } })
  const body = await res.json().catch(() => ({}))
  if (!res.ok) {
    const raw = body.error_description || body.msg || body.message || body.error || 'Supabase Auth request failed'
    const normalized = String(raw).toLowerCase()
    if (res.status === 429 || normalized.includes('rate limit') || normalized.includes('rate_limit')) {
      throw new Error('Supabase email sending is temporarily rate-limited. The built-in email service allows only a small number of emails per hour. Wait before trying another registration, or configure custom SMTP for the project.')
    }
    throw new Error(String(raw))
  }
  return body
}

const scheduleRefresh = () => {
  if (refreshTimer) clearTimeout(refreshTimer)
  refreshTimer = null
  if (!session?.refresh_token || !session?.expires_at) return
  const expiresAtMs = Number(session.expires_at) * 1000
  const delay = Math.max(10000, expiresAtMs - Date.now() - 60000)
  refreshTimer = setTimeout(async () => {
    try { await supabaseAuth.refreshSession() } catch { save(null) }
  }, delay)
}

const save = (next) => {
  session = next
  if (next) localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
  else localStorage.removeItem(STORAGE_KEY)
  scheduleRefresh()
  emit()
  return next
}

export const supabaseAuth = {
  enabled,
  getSession: async () => { scheduleRefresh(); return session },
  onAuthStateChange: (fn) => { listeners.add(fn); return () => listeners.delete(fn) },
  signIn: async (email, password) => save(await request('/auth/v1/token?grant_type=password', { method: 'POST', body: JSON.stringify({ email, password }) })),
  signInWithProvider: async (provider) => {
    if (!['google', 'apple'].includes(provider)) throw new Error('Unsupported sign-in provider')
    localStorage.setItem('maintain-ai-oauth-pending', '1')
    const redirectTo = typeof window !== 'undefined' ? window.location.origin + window.location.pathname : ''
    const url = new URL(SUPABASE_URL + '/auth/v1/authorize')
    url.searchParams.set('provider', provider)
    url.searchParams.set('redirect_to', redirectTo)
    window.location.assign(url.toString())
  },
  isOAuthOnboardingPending: () => localStorage.getItem('maintain-ai-oauth-pending') === '1',
  clearOAuthOnboardingPending: () => localStorage.removeItem('maintain-ai-oauth-pending'),
  signUp: async (email, password, metadata) => save(await request('/auth/v1/signup', { method: 'POST', body: JSON.stringify({ email, password, data: metadata, redirect_to: typeof window !== 'undefined' ? window.location.origin : undefined }) })),
  refreshSession: async () => {
    if (!session?.refresh_token) return null
    return save(await request('/auth/v1/token?grant_type=refresh_token', { method: 'POST', body: JSON.stringify({ refresh_token: session.refresh_token }) }))
  },
  signOut: async () => { if (refreshTimer) clearTimeout(refreshTimer); refreshTimer = null; session = null; localStorage.removeItem(STORAGE_KEY); emit() },
}

scheduleRefresh()
