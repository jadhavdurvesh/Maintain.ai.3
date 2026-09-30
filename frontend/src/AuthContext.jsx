import { createContext, useContext, useEffect, useRef, useState } from 'react'
import api from './api/client.js'
import { getToken, setToken, onUnauthorized, clearApiCache } from './api/client.js'
import { supabaseAuth } from './supabaseAuth.js'
import { setRealtimeOrganizationId } from './realtime.js'

const AuthContext = createContext(null)
const CACHED_USER_KEY = 'maintain-ai-cached-user'

const readCachedUser = () => {
  try {
    const cached = JSON.parse(localStorage.getItem(CACHED_USER_KEY) || 'null')
    return cached?.user_id && cached?.organization_id ? cached : null
  } catch {
    return null
  }
}

const clearCachedUser = () => localStorage.removeItem(CACHED_USER_KEY)

export function AuthProvider({ children }) {
  const [authRequired, setAuthRequired] = useState(null)
  const [user, setUser] = useState(readCachedUser)
  const [checking, setChecking] = useState(true)
  const [needsOnboarding, setNeedsOnboarding] = useState(false)
  const [oauthProfile, setOauthProfile] = useState(null)
  const [authError, setAuthError] = useState(null)
  const [emailConfirmationPending, setEmailConfirmationPending] = useState(() => {
    try { return JSON.parse(localStorage.getItem('maintain-ai-email-confirmation-pending') || 'null') } catch { return null }
  })
  const bootRequestRef = useRef(0)
  const restoreInFlightRef = useRef(null)
  const syncInFlightRef = useRef(null)

  const applyUser = (nextUser) => {
    if (!nextUser) return null
    setUser(nextUser)
    setAuthError(null)
    setRealtimeOrganizationId(nextUser?.organization_id ?? null)
    try { localStorage.setItem(CACHED_USER_KEY, JSON.stringify(nextUser)) } catch {}
    return nextUser
  }

  useEffect(() => {
    const cached = readCachedUser()
    if (cached) setRealtimeOrganizationId(cached.organization_id)
  }, [])

  const syncSupabase = async (metadata = {}) => {
    if (!supabaseAuth.enabled) return null
    if (syncInFlightRef.current) return syncInFlightRef.current
    const request = api.post('/api/auth/supabase/sync', {
      ...metadata,
      registration_mode: supabaseAuth.isOAuthRegistrationPending(),
    })
    syncInFlightRef.current = request
    try {
      const synced = await request
      if (synced?.needs_onboarding) {
        setNeedsOnboarding(true)
        setOauthProfile(synced)
        return synced
      }
      applyUser(synced)
      return synced
    } finally {
      syncInFlightRef.current = null
    }
  }

  const loadMe = () => api.get('/api/auth/me').then((nextUser) => applyUser(nextUser)).catch((error) => {
    setUser(null)
    setRealtimeOrganizationId(null)
    throw error
  })

  const restoreSupabaseUser = async (current) => {
    if (!current?.access_token) return null
    setToken(current.access_token)
    if (restoreInFlightRef.current) return restoreInFlightRef.current

    const request = (async () => {
      try {
        const restored = await api.get('/api/auth/me', { skipUnauthorized: true })
        applyUser(restored)
        setNeedsOnboarding(false)
        return restored
      } catch (error) {
        if (error?.status === 401 || error?.status === 403) {
          return await syncSupabase(current.user?.user_metadata || {})
        }
        throw error
      }
    })()
    restoreInFlightRef.current = request
    try { return await request } finally {
      if (restoreInFlightRef.current === request) restoreInFlightRef.current = null
    }
  }

  useEffect(() => {
    let mounted = true
    const bootId = ++bootRequestRef.current
    const boot = async () => {
      const cachedUser = readCachedUser()
      try {
        let status = null
        let current = null

        if (supabaseAuth.enabled) {
          setAuthRequired(true)
          current = await supabaseAuth.getSession()
        } else {
          status = await api.get('/api/auth/status')
          if (!mounted || bootRequestRef.current !== bootId) return
          setAuthRequired(Boolean(status.auth_required))
        }

        if (!mounted || bootRequestRef.current !== bootId) return

        if (supabaseAuth.enabled) {
          if (current?.access_token) {
            if (cachedUser) {
              applyUser(cachedUser)
              setNeedsOnboarding(false)
            }

            try {
              const restored = await restoreSupabaseUser(current)
              if (!mounted || bootRequestRef.current !== bootId) return
              if (!restored?.needs_onboarding) {
                localStorage.removeItem('maintain-ai-email-confirmation-pending')
                setEmailConfirmationPending(null)
              }
            } catch (error) {
              if (!mounted || bootRequestRef.current !== bootId) return
              if (error?.status === 401 || error?.status === 403) {
                clearCachedUser()
                setUser(null)
                setRealtimeOrganizationId(null)
                setAuthError(error?.message || 'Your session has expired. Please sign in again.')
              } else if (!cachedUser) {
                setAuthError(error?.message || 'Authentication could not be completed.')
              }
            }
          } else {
            clearCachedUser()
            setUser(null)
            setRealtimeOrganizationId(null)
          }
        } else if (status?.auth_required && getToken()) {
          await loadMe()
        }
      } catch (error) {
        if (mounted && bootRequestRef.current === bootId) {
          if (!cachedUser) {
            setAuthRequired(supabaseAuth.enabled)
            setAuthError(error?.message || 'Authentication could not be completed.')
          } else {
            applyUser(cachedUser)
          }
        }
      } finally {
        if (mounted && bootRequestRef.current === bootId) setChecking(false)
      }
    }
    boot()

    const unsubscribe = supabaseAuth.enabled ? supabaseAuth.onAuthStateChange((next) => {
      Promise.resolve().then(async () => {
        try {
          if (next?.access_token) {
            setAuthError(null)
            clearApiCache()
            const restored = await restoreSupabaseUser(next)
            if (restored?.needs_onboarding) setNeedsOnboarding(true)
            window.dispatchEvent(new CustomEvent('maintain-ai-auth-context'))
          } else {
            clearApiCache()
            clearCachedUser()
            setToken(null)
            setUser(null)
            setRealtimeOrganizationId(null)
            window.dispatchEvent(new CustomEvent('maintain-ai-auth-context'))
          }
        } catch (error) {
          if (error?.status === 401 || error?.status === 403) {
            clearCachedUser()
            setUser(null)
            setRealtimeOrganizationId(null)
          } else {
            setAuthError(error?.message || 'Authentication could not be completed.')
          }
        }
      })
    }) : null

    onUnauthorized(() => {
      clearCachedUser()
      setUser(null)
      setAuthError('Your Maintain.ai session was rejected by the backend.')
    })
    return () => { mounted = false; unsubscribe?.() }
  }, [])

  const login = async (email, password) => {
    setAuthError(null)
    if (supabaseAuth.enabled) {
      const s = await supabaseAuth.signIn(email, password)
      await restoreSupabaseUser(s)
      return
    }
    const r = await api.post('/api/auth/login', { email, password })
    setToken(r.access_token)
    await loadMe()
  }

  const register = async (organization_name, username, email, password, full_name) => {
    setAuthError(null)
    if (supabaseAuth.enabled) {
      const s = await supabaseAuth.signUp(email, password, { full_name, username, organization_name })
      if (!s?.access_token) {
        const pending = { email, createdAt: Date.now() }
        localStorage.setItem('maintain-ai-email-confirmation-pending', JSON.stringify(pending))
        setEmailConfirmationPending(pending)
        return { pending_confirmation: true, email }
      }
      setToken(s.access_token)
      const synced = await syncSupabase({ organization_name, username, full_name })
      if (!synced?.needs_onboarding) setNeedsOnboarding(false)
      return
    }
    const r = await api.post('/api/auth/register', { organization_name, username, email, password, full_name })
    setToken(r.access_token)
    await loadMe()
  }

  const resendEmailConfirmation = async () => {
    if (!emailConfirmationPending?.email) return
    await supabaseAuth.resendSignupConfirmation(emailConfirmationPending.email)
  }

  const checkEmailConfirmation = async () => {
    const current = await supabaseAuth.getSession()
    if (!current?.access_token) return false
    const synced = await syncSupabase(current.user?.user_metadata || {})
    if (synced?.needs_onboarding) {
      setNeedsOnboarding(true)
      setOauthProfile(synced)
      return false
    }
    setNeedsOnboarding(false)
    localStorage.removeItem('maintain-ai-email-confirmation-pending')
    setEmailConfirmationPending(null)
    return true
  }

  const cancelEmailConfirmation = () => {
    localStorage.removeItem('maintain-ai-email-confirmation-pending')
    setEmailConfirmationPending(null)
  }

  const completeOnboarding = async (organization_name, username, full_name) => {
    setAuthError(null)
    const synced = await syncSupabase({ organization_name, username, full_name })
    if (synced?.needs_onboarding) throw new Error('Organization and username are required.')
    setNeedsOnboarding(false)
    setOauthProfile(null)
    supabaseAuth.clearOAuthOnboardingPending()
    return synced
  }

  const logout = async () => {
    if (supabaseAuth.enabled) await supabaseAuth.signOut()
    clearApiCache()
    clearCachedUser()
    setToken(null)
    setUser(null)
    setRealtimeOrganizationId(null)
    window.dispatchEvent(new CustomEvent('maintain-ai-auth-context'))
  }

  const needsLogin = authRequired === true && !user
  return <AuthContext.Provider value={{ authRequired, user, checking, needsLogin, needsOnboarding, oauthProfile, authError, emailConfirmationPending, login, register, resendEmailConfirmation, checkEmailConfirmation, cancelEmailConfirmation, completeOnboarding, logout }}>{children}</AuthContext.Provider>
}
export function useAuth() { return useContext(AuthContext) }
