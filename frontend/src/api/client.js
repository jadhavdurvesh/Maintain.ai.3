const BASE_URL = import.meta.env.VITE_API_URL || ''
const TOKEN_KEY = 'maintain-ai-token'

export function getToken() {
  return localStorage.getItem(TOKEN_KEY)
}
export function setToken(token) {
  if (token) localStorage.setItem(TOKEN_KEY, token)
  else localStorage.removeItem(TOKEN_KEY)
}

const GET_CACHE_TTL_MS = 15000
const getCache = new Map()
const getInFlight = new Map()

export function clearApiCache(pathPrefix = '') {
  for (const key of getCache.keys()) if (!pathPrefix || key.startsWith(pathPrefix)) getCache.delete(key)
}

let unauthorizedHandler = null
export function onUnauthorized(fn) {
  unauthorizedHandler = fn
}

async function request(path, options = {}) {
  const method = (options.method || 'GET').toUpperCase()
  const isGet = method === 'GET'
  const now = Date.now()
  if (isGet) {
    const cached = getCache.get(path)
    if (cached && now - cached.time < GET_CACHE_TTL_MS) return cached.data
    const pending = getInFlight.get(path)
    if (pending) return pending
  }
  const token = getToken()
  const headers = { 'Content-Type': 'application/json', ...(options.headers || {}) }
  if (token) headers['Authorization'] = `Bearer ${token}`

  const fetchPromise = fetch(`${BASE_URL}${path}`, { ...options, headers })
  if (isGet) getInFlight.set(path, fetchPromise)
  const res = await fetchPromise

  if (res.status === 401) {
    setToken(null)
    if (unauthorizedHandler) unauthorizedHandler()
  }
  if (isGet) getInFlight.delete(path)
  if (!isGet) clearApiCache()
  if (!res.ok) {
    const body = await res.text()
    throw new Error(`${res.status} ${res.statusText}: ${body}`)
  }
  const contentType = res.headers.get('content-type') || ''
  if (contentType.includes('application/json')) {
    const data = await res.json()
    if (isGet) getCache.set(path, { time: Date.now(), data })
    return data
  }
  const data = await res.text()
  if (isGet) getCache.set(path, { time: Date.now(), data })
  return data
}

export const api = {
  get: (path) => request(path),
  post: (path, body) => request(path, { method: 'POST', body: JSON.stringify(body) }),
  patch: (path, body) => request(path, { method: 'PATCH', body: JSON.stringify(body) }),
  del: (path) => request(path, { method: 'DELETE' }),
}

export default api
