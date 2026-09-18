const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL || ''
const SUPABASE_KEY = import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY || ''
const STORAGE_KEY = 'maintain-ai-supabase-session'
const enabled = Boolean(SUPABASE_URL && SUPABASE_KEY)
let session = null; let listeners = new Set()
try { session = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null') } catch {}
const emit = () => listeners.forEach(fn => fn(session))
const request = async (path, options = {}) => {
  const res = await fetch(`${SUPABASE_URL}${path}`, { ...options, headers: { apikey: SUPABASE_KEY, 'Content-Type': 'application/json', ...(options.headers || {}) } })
  const body = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(body.error_description || body.msg || body.message || 'Supabase Auth request failed')
  return body
}
const save = (next) => { session = next; if (next) localStorage.setItem(STORAGE_KEY, JSON.stringify(next)); else localStorage.removeItem(STORAGE_KEY); emit(); return next }
export const supabaseAuth = {
  enabled, getSession: async () => session,
  onAuthStateChange: (fn) => { listeners.add(fn); return () => listeners.delete(fn) },
  signIn: async (email, password) => save(await request('/auth/v1/token?grant_type=password', { method: 'POST', body: JSON.stringify({ email, password }) })),
  signUp: async (email, password, metadata) => save(await request('/auth/v1/signup', { method: 'POST', body: JSON.stringify({ email, password, data: metadata }) })),
  signOut: async () => { session = null; localStorage.removeItem(STORAGE_KEY); emit() },
}