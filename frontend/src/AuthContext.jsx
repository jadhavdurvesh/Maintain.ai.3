import { createContext, useContext, useEffect, useState } from 'react'
import api from './api/client.js'
import { getToken, setToken, onUnauthorized } from './api/client.js'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  // authRequired: null while we haven't checked yet (avoids a login-screen
  // flash for the common case — local mode — where it's always false)
  const [authRequired, setAuthRequired] = useState(null)
  const [user, setUser] = useState(null)
  const [checking, setChecking] = useState(true)

  const loadMe = () => api.get('/api/auth/me').then(setUser).catch(() => setUser(null))

  useEffect(() => {
    api.get('/api/auth/status')
      .then(async (status) => {
        setAuthRequired(status.auth_required)
        if (status.auth_required && getToken()) {
          await loadMe()
        }
      })
      .catch(() => setAuthRequired(false))
      .finally(() => setChecking(false))

    onUnauthorized(() => setUser(null))
  }, [])

  const login = async (email, password) => {
    const result = await api.post('/api/auth/login', { email, password })
    setToken(result.access_token)
    await loadMe()
  }

  const register = async (organization_name, username, email, password, full_name) => {
    const result = await api.post('/api/auth/register', { organization_name, username, email, password, full_name })
    setToken(result.access_token)
    await loadMe()
  }

  const logout = () => {
    setToken(null)
    setUser(null)
  }

  const needsLogin = authRequired === true && !user

  return (
    <AuthContext.Provider value={{ authRequired, user, checking, needsLogin, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}
