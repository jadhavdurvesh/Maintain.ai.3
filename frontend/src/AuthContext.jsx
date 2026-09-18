import { createContext, useContext, useEffect, useState } from 'react'
import api from './api/client.js'
import { getToken, setToken, onUnauthorized } from './api/client.js'
import { supabaseAuth } from './supabaseAuth.js'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [authRequired, setAuthRequired] = useState(null)
  const [user, setUser] = useState(null)
  const [checking, setChecking] = useState(true)
  const loadMe = () => api.get('/api/auth/me').then(setUser).catch(() => setUser(null))

  useEffect(() => {
    let mounted = true
    const boot = async () => {
      try {
        const status = await api.get('/api/auth/status')
        if (!mounted) return
        setAuthRequired(status.auth_required || supabaseAuth.enabled)
        if (supabaseAuth.enabled) {
          const current = await supabaseAuth.getSession()
          if (current?.access_token) { setToken(current.access_token); await loadMe() }
        } else if (status.auth_required && getToken()) await loadMe()
      } catch { if (mounted) setAuthRequired(supabaseAuth.enabled) }
      finally { if (mounted) setChecking(false) }
    }
    boot()
    const unsubscribe = supabaseAuth.enabled ? supabaseAuth.onAuthStateChange(async (next) => {
      if (next?.access_token) { setToken(next.access_token); await loadMe() } else { setToken(null); setUser(null) }
    }) : null
    onUnauthorized(() => setUser(null))
    return () => { mounted = false; unsubscribe?.() }
  }, [])

  const login = async (email, password) => {
    if (supabaseAuth.enabled) { const s = await supabaseAuth.signIn(email, password); setToken(s.access_token); await loadMe(); return }
    const r = await api.post('/api/auth/login', { email, password }); setToken(r.access_token); await loadMe()
  }
  const register = async (organization_name, username, email, password, full_name) => {
    if (supabaseAuth.enabled) {
      const s = await supabaseAuth.signUp(email, password, { full_name, username, organization_name })
      if (!s?.access_token) throw new Error('Account created. Check your email to confirm the account, then sign in.')
      setToken(s.access_token); await api.post('/api/auth/supabase/sync', { organization_name, username, full_name }); await loadMe(); return
    }
    const r = await api.post('/api/auth/register', { organization_name, username, email, password, full_name }); setToken(r.access_token); await loadMe()
  }
  const logout = async () => { if (supabaseAuth.enabled) await supabaseAuth.signOut(); setToken(null); setUser(null) }
  const needsLogin = authRequired === true && !user
  return <AuthContext.Provider value={{ authRequired, user, checking, needsLogin, login, register, logout }}>{children}</AuthContext.Provider>
}
export function useAuth() { return useContext(AuthContext) }
