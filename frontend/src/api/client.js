const BASE_URL = import.meta.env.VITE_API_URL || ''
const ML_BASE_URL = import.meta.env.VITE_ML_SERVICE_URL || 'https://maintain-ai-ml.onrender.com'
const TOKEN_KEY = 'maintain-ai-token'
export function getToken() { return localStorage.getItem(TOKEN_KEY) }
export function setToken(token) { if (token) localStorage.setItem(TOKEN_KEY, token); else localStorage.removeItem(TOKEN_KEY) }
const GET_CACHE_TTL_MS = 15000, getCache = new Map(), getInFlight = new Map()
export function clearApiCache(prefix = '') { for (const key of getCache.keys()) if (!prefix || key.startsWith(prefix)) getCache.delete(key) }
let unauthorizedHandler = null; export function onUnauthorized(fn) { unauthorizedHandler = fn }
let desktopBasePromise
async function getApiBaseUrl() { if (typeof window !== 'undefined' && window.maintainAI) { desktopBasePromise ||= window.maintainAI.backendUrl(); return desktopBasePromise } return BASE_URL }

function isExecutionRequest(path) {
  return path.startsWith('/api/predictions/') && (
    path.includes('/forecast?') ||
    path.includes('/windows/run?') ||
    path.includes('/windows/compare?')
  )
}

async function runRemoteChronosForecast(path, base, headers, signal) {
  const match = path.match(/^\/api\/analytics\/machines\/([^/]+)\/forecast\?(.*)$/)
  if (!match) return null
  const params = new URLSearchParams(match[2])
  const model = params.get('model') || 'chronos2'
  if (model !== 'chronos2') return null
  const readingType = params.get('reading_type') || 'temperature'
  const horizon = Math.max(1, Math.min(64, Number(params.get('horizon') || 12)))
  const machineId = decodeURIComponent(match[1])

  const readingsResponse = await fetch(`${base}/api/machines/${encodeURIComponent(machineId)}/readings?limit=200`, { headers, signal })
  if (!readingsResponse.ok) {
    const body = await readingsResponse.text()
    throw new Error(readingsResponse.status + ' ' + readingsResponse.statusText + ': ' + body)
  }
  const readings = await readingsResponse.json()
  const values = (Array.isArray(readings) ? readings : [])
    .filter(r => r.reading_type === readingType)
    .sort((a, b) => new Date(a.recorded_at) - new Date(b.recorded_at))
    .map(r => Number(r.value))
    .filter(Number.isFinite)

  if (values.length < 32) {
    return { available: false, model: 'amazon/chronos-2', forecast: [], horizon, reason: `At least 32 ${readingType} samples are required; only ${values.length} are available.` }
  }

  const mlResponse = await fetch(`${ML_BASE_URL}/v1/forecast`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ model: 'amazon/chronos-2', values: values.slice(-128), horizon }),
    signal,
  })
  if (!mlResponse.ok) {
    const body = await mlResponse.text()
    throw new Error(mlResponse.status + ' ' + mlResponse.statusText + ': ' + body)
  }
  return await mlResponse.json()
}

async function request(path, options = {}) {
  const method = (options.method || 'GET').toUpperCase()
  const isGet = method === 'GET'
  const executionRequest = isGet && isExecutionRequest(path)
  const isRemoteForecast = isGet && path.startsWith('/api/analytics/machines/') && path.includes('/forecast?') && new URLSearchParams(path.split('?')[1] || '').get('model') === 'chronos2'
  const cacheableGet = isGet && !executionRequest
  const now = Date.now()
  if (cacheableGet) {
    const c = getCache.get(path)
    if (c && now - c.time < GET_CACHE_TTL_MS) return c.data
    const p = getInFlight.get(path)
    if (p) return p
  }
  const token = getToken()
  const headers = { 'Content-Type': 'application/json', 'X-Maintain-Application': 'engineering', ...(options.headers || {}) }
  if (token) headers.Authorization = 'Bearer ' + token
  const controller = new AbortController()
  const timeoutMs = isRemoteForecast ? 75000 : 20000
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs)
  const base = await getApiBaseUrl()
  let fp
  if (isRemoteForecast) {
    fp = runRemoteChronosForecast(path, base, headers, controller.signal).catch(err => {
      if (err?.name === 'AbortError' || controller.signal.aborted) throw new Error(`Chronos inference timed out after ${timeoutMs / 1000}s`)
      throw err
    }).finally(() => window.clearTimeout(timeout))
  } else {
    fp = fetch(base + path, { ...options, headers, signal: controller.signal }).catch(err => {
      if (err?.name === 'AbortError' || controller.signal.aborted) {
        throw new Error(`Request timed out after 20s: ${method} ${path}`)
      }
      throw err
    }).finally(() => window.clearTimeout(timeout)).then(async res => {
      if (res.status === 401) {
        setToken(null)
        if (unauthorizedHandler) unauthorizedHandler()
      }
      if (!res.ok) {
        const body = await res.text()
        throw new Error(res.status + ' ' + res.statusText + ': ' + body)
      }
      const ct = res.headers.get('content-type') || ''
      return ct.includes('application/json') ? await res.json() : await res.text()
    })
  }

  if (cacheableGet) getInFlight.set(path, fp)
  try {
    const data = await fp
    if (cacheableGet) getCache.set(path, { time: Date.now(), data })
    return data
  } finally {
    if (cacheableGet && getInFlight.get(path) === fp) getInFlight.delete(path)
  }
}
export const api = { get: p => request(p), post: (p, b) => request(p, { method: 'POST', body: JSON.stringify(b) }), patch: (p, b) => request(p, { method: 'PATCH', body: JSON.stringify(b) }), put: (p, b) => request(p, { method: 'PUT', body: JSON.stringify(b) }), del: p => request(p, { method: 'DELETE' }) }; export default api
