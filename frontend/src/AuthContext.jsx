import { createContext, useContext, useEffect, useRef, useState } from 'react'
import api from './api/client.js'
import { getToken, setToken, onUnauthorized, clearApiCache } from './api/client.js'
import { supabaseAuth } from './supabaseAuth.js'
import { setRealtimeOrganizationId } from './realtime.js'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [authRequired, setAuthRequired] = useState(null)
  const [user, setUser] = useState(null)
  const [checking, setChecking] = useState(true)
  const [needsOnboarding, setNeedsOnboarding] = useState(false)
  const [oauthProfile, setOauthProfile] = useState(null)
  const [authError, setAuthError] = useState(null)
  const [emailConfirmationPending, setEmailConfirmationPending] = useState(() => {
    try { return JSON.parse(localStorage.getItem('maintain-ai-email-confirmation-pending') || 'null') } catch { return null }
  })

  const syncSupabase = async (metadata = {}) => {
    if (!supabaseAuth.enabled) return null
    const synced = await api.post('/api/auth/supabase/sync', {
      ...metadata,
      registration_mode: supabaseAuth.isOAuthRegistrationPending(),
    })
    if (synced?.needs_onboarding) {
      setNeedsOnboarding(true)
      setOauthProfile(synced)
      return synced
    }
    // Do not refresh here. refreshSession() emits auth-state-change, which
    // would call syncSupabase() again and create a callback/sync loop.
    return synced
  }

  const loadMe = () => api.get('/api/auth/me').then((nextUser) => {
    setUser(nextUser)
    setAuthError(null)
    setRealtimeOrganizationId(nextUser?.organization_id ?? null)
    return nextUser
  }).catch((error) => {
    setUser(null)
    setRealtimeOrganizationId(null)
    throw error
  })

  useEffect(() => {
    let mounted = true
    const boot = async () => {
      try {
        const status = await api.get('/api/auth/status')
        if (!mounted) return
        setAuthRequired(status.auth_required || supabaseAuth.enabled)
        if (supabaseAuth.enabled) {
          const current = await supabaseAuth.getSession()
          if (current?.access_token) {
            setToken(current.access_token)
            const synced = await syncSupabase(current.user?.user_metadata || {})
            if (!synced?.needs_onboarding) {
              await loadMe()
              localStorage.removeItem('maintain-ai-email-confirmation-pending')
              setEmailConfirmationPending(null)
            }
          }
        } else if (status.auth_required && getToken()) {
          await loadMe()
        }
      } catch (error) {
        if (mounted) {
          setAuthRequired(supabaseAuth.enabled)
          setAuthError(error?.message || 'Authentication could not be completed.')
        }
      } finally {
        if (mounted) setChecking(false)
      }
    }
    boot()

    const unsubscribe = supabaseAuth.enabled ? supabaseAuth.onAuthStateChange(async (next) => {
      try {
        if (next?.access_token) {
          setAuthError(null)
          clearApiCache()
          setToken(next.access_token)
          window.dispatchEvent(new CustomEvent('maintain-ai-auth-context'))
          const synced = await syncSupabase(next.user?.user_metadata || {})
          if (!synced?.needs_onboarding) await loadMe()
        } else {
          clearApiCache()
          setToken(null)
          setUser(null)
          setRealtimeOrganizationId(null)
          window.dispatchEvent(new CustomEvent('maintain-ai-auth-context'))
        }
      } catch (error) {
        setAuthError(error?.message || 'Authentication could not be completed.')
      }
    }) : null

    onUnauthorized(() => {
      setUser(null)
      setAuthError('Your Maintain.ai session was rejected by the backend.')
    })
    return () => { mounted = false; unsubscribe?.() }
  }, [])

  const login = async (email, password) => {
    setAuthError(null)
    if (supabaseAuth.enabled) {
      const s = await supabaseAuth.signIn(email, password)
      setToken(s.access_token)
      const synced = await syncSupabase(s.user?.user_metadata || {})
      if (!synced?.needs_onboarding) await loadMe()
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
      if (!synced?.needs_onboarding) await loadMe()
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
    setToken(current.access_token)
    const synced = await syncSupabase(current.user?.user_metadata || {})
    if (synced?.needs_onboarding) {
      setNeedsOnboarding(true)
      setOauthProfile(synced)
      return false
    }
    await loadMe()
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
    await loadMe()
    return synced
  }

  const logout = async () => {
    if (supabaseAuth.enabled) await supabaseAuth.signOut()
    clearApiCache()
    setToken(null)
    setUser(null)
    setRealtimeOrganizationId(null)
  }

  const needsLogin = authRequired === true && !user
  return <AuthContext.Provider value={{ authRequired, user, checking, needsLogin, needsOnboarding, oauthProfile, authError, emailConfirmationPending, login, register, resendEmailConfirmation, checkEmailConfirmation, cancelEmailConfirmation, completeOnboarding, logout }}>{children}</AuthContext.Provider>
}
export function useAuth() { return useContext(AuthContext) }
