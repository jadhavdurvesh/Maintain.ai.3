const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL || ''
const SUPABASE_KEY = import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY || ''
const STORAGE_KEY = 'maintain-ai-supabase-session'
const PKCE_VERIFIER_KEY = 'maintain-ai-supabase-pkce-verifier'
const PKCE_STATE_KEY = 'maintain-ai-supabase-pkce-state'
const enabled = Boolean(SUPABASE_URL && SUPABASE_KEY)
let session = null
let refreshTimer = null
const listeners = new Set()

try { session = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null') } catch {}

const request = async (path, options = {}) => {
  const res = await fetch(SUPABASE_URL + path, {
    ...options,
    headers: {
      apikey: SUPABASE_KEY,
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    },
  })
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

const base64Url = (bytes) => {
  let binary = ''
  bytes.forEach(byte => { binary += String.fromCharCode(byte) })
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/g, '')
}

const randomString = (length = 32) => {
  const bytes = new Uint8Array(length)
  crypto.getRandomValues(bytes)
  return base64Url(bytes)
}

const createPkce = async () => {
  const verifier = randomString(48)
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(verifier))
  return { verifier, challenge: base64Url(new Uint8Array(digest)) }
}

const hydrateUser = async (next) => {
  if (!next?.access_token || next.user) return next
  try {
    const user = await request('/auth/v1/user', {
      headers: { Authorization: 'Bearer ' + next.access_token },
    })
    return { ...next, user }
  } catch {
    return next
  }
}

const emit = () => {
  listeners.forEach(fn => fn(session))
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent('maintain-ai-auth-context', {
      detail: session ? { access_token: session.access_token || null } : null,
    }))
  }
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

const saveTokenResponse = async (tokens) => {
  const next = {
    ...tokens,
    expires_at: Number(tokens.expires_at || (Math.floor(Date.now() / 1000) + Number(tokens.expires_in || 3600))),
  }
  return save(await hydrateUser(next))
}

const clearOAuthParams = () => {
  if (typeof window === 'undefined') return
  window.history.replaceState({}, document.title, window.location.pathname + window.location.hash)
}

const consumeOAuthCallback = async () => {
  if (typeof window === 'undefined') return null
  const params = new URLSearchParams(window.location.search)
  const error = params.get('error')
  if (error) {
    const description = params.get('error_description') || error
    clearOAuthParams()
    throw new Error(description)
  }

  const code = params.get('code')
  if (code) {
    const expectedState = sessionStorage.getItem(PKCE_STATE_KEY)
    const returnedState = params.get('state')
    if (!expectedState || !returnedState || expectedState !== returnedState) {
      clearOAuthParams()
      sessionStorage.removeItem(PKCE_VERIFIER_KEY)
      sessionStorage.removeItem(PKCE_STATE_KEY)
      throw new Error('OAuth security check failed. Please start Google or Apple sign-in again.')
    }

    const verifier = sessionStorage.getItem(PKCE_VERIFIER_KEY)
    if (!verifier) {
      clearOAuthParams()
      throw new Error('The Google/Apple sign-in session expired. Please start sign-in again.')
    }

    const tokens = await request('/auth/v1/token?grant_type=pkce', {
      method: 'POST',
      body: JSON.stringify({ auth_code: code, code_verifier: verifier }),
    })

    sessionStorage.removeItem(PKCE_VERIFIER_KEY)
    sessionStorage.removeItem(PKCE_STATE_KEY)
    clearOAuthParams()
    return saveTokenResponse(tokens)
  }

  const hash = new URLSearchParams(window.location.hash.replace(/^#/, ''))
  const accessToken = hash.get('access_token')
  const refreshToken = hash.get('refresh_token')
  if (accessToken && refreshToken) {
    const tokens = {
      access_token: accessToken,
      refresh_token: refreshToken,
      expires_in: Number(hash.get('expires_in') || 3600),
      expires_at: Math.floor(Date.now() / 1000) + Number(hash.get('expires_in') || 3600),
      token_type: hash.get('token_type') || 'bearer',
      user: null,
    }
    window.history.replaceState({}, document.title, window.location.pathname + window.location.search)
    return saveTokenResponse(tokens)
  }

  return null
}

const hydrateStoredSession = async () => {
  if (!session?.access_token || session.user) return session
  return save(await hydrateUser(session))
}

export const supabaseAuth = {
  enabled,

  getSession: async () => {
    const callbackSession = await consumeOAuthCallback()
    const current = callbackSession || await hydrateStoredSession()
    scheduleRefresh()
    return current
  },

  onAuthStateChange: (fn) => {
    listeners.add(fn)
    return () => listeners.delete(fn)
  },

  signIn: async (email, password) =>
    save(await hydrateUser(await request('/auth/v1/token?grant_type=password', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }))),

  signInWithProvider: async (provider) => {
    if (!['google', 'apple'].includes(provider)) throw new Error('Unsupported sign-in provider')
    if (typeof window === 'undefined') return

    const { verifier, challenge } = await createPkce()
    const state = randomString(24)
    sessionStorage.setItem(PKCE_VERIFIER_KEY, verifier)
    sessionStorage.setItem(PKCE_STATE_KEY, state)
    localStorage.setItem('maintain-ai-oauth-pending', '1')

    const redirectTo = window.location.origin + window.location.pathname
    const url = new URL(SUPABASE_URL + '/auth/v1/authorize')
    url.searchParams.set('provider', provider)
    url.searchParams.set('redirect_to', redirectTo)
    url.searchParams.set('flow_type', 'pkce')
    url.searchParams.set('code_challenge', challenge)
    url.searchParams.set('code_challenge_method', 's256')
    url.searchParams.set('state', state)
    window.location.assign(url.toString())
  },

  isOAuthOnboardingPending: () =>
    localStorage.getItem('maintain-ai-oauth-pending') === '1',

  clearOAuthOnboardingPending: () =>
    localStorage.removeItem('maintain-ai-oauth-pending'),

  signUp: async (email, password, metadata) =>
    save(await hydrateUser(await request('/auth/v1/signup', {
      method: 'POST',
      body: JSON.stringify({
        email,
        password,
        data: metadata,
        redirect_to: typeof window !== 'undefined' ? window.location.origin : undefined,
      }),
    }))),

  refreshSession: async () => {
    if (!session?.refresh_token) return null
    return save(await hydrateUser(await request('/auth/v1/token?grant_type=refresh_token', {
      method: 'POST',
      body: JSON.stringify({ refresh_token: session.refresh_token }),
    })))
  },

  signOut: async () => {
    if (refreshTimer) clearTimeout(refreshTimer)
    refreshTimer = null
    session = null
    localStorage.removeItem(STORAGE_KEY)
    sessionStorage.removeItem(PKCE_VERIFIER_KEY)
    sessionStorage.removeItem(PKCE_STATE_KEY)
    localStorage.removeItem('maintain-ai-oauth-pending')
    emit()
  },
}

scheduleRefresh()
