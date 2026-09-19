import { createContext, useContext, useEffect, useRef, useState } from 'react'
import api from './api/client.js'
import { getToken, setToken, onUnauthorized } from './api/client.js'
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
            if (!synced?.needs_onboarding) await loadMe()
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
          setToken(next.access_token)
          const synced = await syncSupabase(next.user?.user_metadata || {})
          if (!synced?.needs_onboarding) await loadMe()
        } else {
          setToken(null)
          setUser(null)
          setRealtimeOrganizationId(null)
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
      if (!s?.access_token) throw new Error('Account created. Check your email to confirm the account, then sign in.')
      setToken(s.access_token)
      await syncSupabase({ organization_name, username, full_name })
      await loadMe()
      return
    }
    const r = await api.post('/api/auth/register', { organization_name, username, email, password, full_name })
    setToken(r.access_token)
    await loadMe()
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
    setToken(null)
    setUser(null)
    setRealtimeOrganizationId(null)
  }

  const needsLogin = authRequired === true && !user
  return <AuthContext.Provider value={{ authRequired, user, checking, needsLogin, needsOnboarding, oauthProfile, authError, login, register, completeOnboarding, logout }}>{children}</AuthContext.Provider>
}
export function useAuth() { return useContext(AuthContext) }
