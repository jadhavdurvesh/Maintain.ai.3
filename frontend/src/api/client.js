const BASE_URL = import.meta.env.VITE_API_URL || ''
const TOKEN_KEY = 'maintain-ai-token'
export function getToken() { return localStorage.getItem(TOKEN_KEY) }
export function setToken(token) { if (token) localStorage.setItem(TOKEN_KEY, token); else localStorage.removeItem(TOKEN_KEY) }
const GET_CACHE_TTL_MS = 15000, getCache = new Map(), getInFlight = new Map()
export function clearApiCache(prefix = '') { for (const key of getCache.keys()) if (!prefix || key.startsWith(prefix)) getCache.delete(key) }
let unauthorizedHandler = null; export function onUnauthorized(fn) { unauthorizedHandler = fn }
let desktopBasePromise
async function getApiBaseUrl() { if (typeof window !== 'undefined' && window.maintainAI) { desktopBasePromise ||= window.maintainAI.backendUrl(); return desktopBasePromise } return BASE_URL }
async function request(path, options = {}) {
  const method = (options.method || 'GET').toUpperCase()
  const isGet = method === 'GET'
  const now = Date.now()
  if (isGet) {
    const c = getCache.get(path)
    if (c && now - c.time < GET_CACHE_TTL_MS) return c.data
    const p = getInFlight.get(path)
    if (p) return p
  }
  const token = getToken()
  const headers = { 'Content-Type': 'application/json', 'X-Maintain-Application': 'engineering', ...(options.headers || {}) }
  if (token) headers.Authorization = 'Bearer ' + token
  const controller = new AbortController()
  const timeout = window.setTimeout(() => controller.abort(), 20000)
  const base = await getApiBaseUrl()
  const fp = fetch(base + path, { ...options, headers, signal: controller.signal }).catch(err => {
    if (err?.name === 'AbortError' || controller.signal.aborted) {
      throw new Error(`Request timed out after 20s: ${method} ${path}`)
    }
    throw err
  }).finally(() => window.clearTimeout(timeout))

  if (isGet) getInFlight.set(path, fp)
  try {
    const res = await fp
    if (res.status === 401) {
      setToken(null)
      if (unauthorizedHandler) unauthorizedHandler()
    }
    if (!res.ok) {
      const body = await res.text()
      throw new Error(res.status + ' ' + res.statusText + ': ' + body)
    }
    const ct = res.headers.get('content-type') || ''
    const data = ct.includes('application/json') ? await res.json() : await res.text()
    if (isGet) getCache.set(path, { time: Date.now(), data })
    return data
  } finally {
    // Always release an in-flight GET, including network errors, timeouts and 4xx/5xx responses.
    // Otherwise a failed request can poison this cache until a full page reload.
    if (isGet && getInFlight.get(path) === fp) getInFlight.delete(path)
  }
}
export const api = { get: p => request(p), post: (p, b) => request(p, { method: 'POST', body: JSON.stringify(b) }), patch: (p, b) => request(p, { method: 'PATCH', body: JSON.stringify(b) }), put: (p, b) => request(p, { method: 'PUT', body: JSON.stringify(b) }), del: p => request(p, { method: 'DELETE' }) }; export default api
