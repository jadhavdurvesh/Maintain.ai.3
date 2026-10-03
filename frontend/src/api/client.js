const BASE_URL = import.meta.env.VITE_API_URL || ''
const ML_BASE_URL = import.meta.env.VITE_ML_SERVICE_URL || 'https://maintain-ai-ml.onrender.com'
const TOKEN_KEY = 'maintain-ai-token'
export function getToken() { return localStorage.getItem(TOKEN_KEY) }
export function setToken(token) { if (token) localStorage.setItem(TOKEN_KEY, token); else localStorage.removeItem(TOKEN_KEY) }
const GET_CACHE_TTL_MS = 60000
const getCache = new Map()
const getInFlight = new Map()
const getSubscribers = new Map()

export function clearApiCache(prefix = '') {
  for (const key of getCache.keys()) if (!prefix || key.startsWith(prefix)) getCache.delete(key)
}

export function subscribeApiCache(path, fn) {
  if (!getSubscribers.has(path)) getSubscribers.set(path, new Set())
  getSubscribers.get(path).add(fn)
  return () => getSubscribers.get(path)?.delete(fn)
}

function publishApiCache(path, data) {
  for (const fn of getSubscribers.get(path) || []) {
    try { fn(data) } catch {}
  }
}
let unauthorizedHandler = null; export function onUnauthorized(fn) { unauthorizedHandler = fn }
let desktopBasePromise
async function getApiBaseUrl() { if (typeof window !== 'undefined' && window.maintainAI) { desktopBasePromise ||= window.maintainAI.backendUrl(); return desktopBasePromise } return BASE_URL }

function isPredictionPath(path) { return path.startsWith('/api/predictions/') }
function isNotFoundResponse(res) { return res.status === 404 }

async function predictionCompatibility(path, base, headers, signal) {
  const match = path.match(/^\/api\/predictions\/machines\/([^/]+)\/(status|history|windows(?:\/run)?)\?(.*)$/)
  if (!match) return null
  const machineId = decodeURIComponent(match[1])
  const action = match[2]
  const params = new URLSearchParams(match[3])
  const readingType = params.get('reading_type') || 'temperature'
  const model = params.get('model') || 'chronos-bolt-tiny'
  const horizon = Math.max(1, Math.min(64, Number(params.get('horizon') || 12)))

  const readingsResponse = await fetch(`${base}/api/machines/${encodeURIComponent(machineId)}/readings?limit=64`, { headers, signal })
  if (!readingsResponse.ok) return null
  const readings = await readingsResponse.json()
  const rows = (Array.isArray(readings) ? readings : []).filter(r => r.reading_type === readingType).sort((a,b) => new Date(a.recorded_at) - new Date(b.recorded_at))
  const latest = rows[rows.length - 1] || null
  const telemetryActive = !!latest && (Date.now() - new Date(latest.recorded_at).getTime()) <= 15 * 60 * 1000

  if (action === 'status') {
    return { machine_id:Number(machineId), reading_type:readingType, model, horizon, telemetry_active:telemetryActive, latest_telemetry_at:latest?.recorded_at || null, latest_telemetry_id:latest?.id || null, latest_value:latest?.value == null ? null : Number(latest.value), sample_count:rows.length, interval_seconds:300, minimum_samples:32, latest_run:null, compatibility:true }
  }

  if (action === 'history') return { machine_id:Number(machineId), reading_type:readingType, model, horizon:params.get('horizon') ? horizon : null, forecast_window:params.get('forecast_window') || null, runs:[], count:0, generated_at:new Date().toISOString(), compatibility:true }

  if (action === 'windows') {
    const names = ['24h','48h','7d','30d']
    if (!path.includes('/run?')) return { machine_id:Number(machineId), reading_type:readingType, model, windows:Object.fromEntries(names.map(name => [name,{available:false,window:name,reason:'Waiting for the prediction API deployment.'}])), compatibility:true }
    return { available:false, window:params.get('window') || '24h', reason:'The window prediction API is still deploying. Use the short forecast while it becomes available.', compatibility:true }
  }
  return null
}

function isExecutionRequest(path) {
  return path.startsWith('/api/predictions/') && (path.includes('/forecast?') || path.includes('/windows/run?') || path.includes('/windows/compare?'))
}

async function runRemoteChronosForecast(path, base, headers, signal) {
  const match = path.match(/^\/api\/analytics\/machines\/([^/]+)\/forecast\?(.*)$/)
  if (!match) return null
  const params = new URLSearchParams(match[2])
  const model = params.get('model') || 'chronos2'
  const readingType = params.get('reading_type') || 'temperature'
  const horizon = Math.max(1, Math.min(64, Number(params.get('horizon') || 12)))
  const machineId = decodeURIComponent(match[1])
  const readingsResponse = await fetch(`${base}/api/machines/${encodeURIComponent(machineId)}/readings?limit=200`, { headers, signal })
  if (!readingsResponse.ok) { const body = await readingsResponse.text(); throw new Error(readingsResponse.status + ' ' + readingsResponse.statusText + ': ' + body) }
  const readings = await readingsResponse.json()
  const values = (Array.isArray(readings) ? readings : []).filter(r => r.reading_type === readingType).sort((a,b) => new Date(a.recorded_at) - new Date(b.recorded_at)).map(r => Number(r.value)).filter(Number.isFinite)
  if (values.length < 32) return { available:false, model:model === 'timer' ? 'timer' : 'chronos2', forecast:[], horizon, reason:`At least 32 ${readingType} samples are required; only ${values.length} are available.` }
  const mlResponse = await fetch(`${ML_BASE_URL}/v1/forecast`, { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ model:model === 'timer' ? 'timer' : 'amazon/chronos-2', values:values.slice(-128), horizon }), signal })
  if (!mlResponse.ok) { const body = await mlResponse.text(); throw new Error(mlResponse.status + ' ' + mlResponse.statusText + ': ' + body) }
  return await mlResponse.json()
}

async function request(path, options = {}) {
  const method = (options.method || 'GET').toUpperCase()
  const bypassCache = options.cache === 'no-store'
  const isGet = method === 'GET'
  const executionRequest = isGet && isExecutionRequest(path)
  const isRemoteForecast = isGet && path.startsWith('/api/analytics/machines/') && path.includes('/forecast?') && new URLSearchParams(path.split('?')[1] || '').get('model') === 'chronos2'
  const explicitlyFresh = /(?:\?|&)ts=/.test(path)
  const cacheableGet = isGet && !executionRequest && !bypassCache && !explicitlyFresh
  const now = Date.now()
  if (cacheableGet) {
    const c = getCache.get(path)
    const p = getInFlight.get(path)
    if (c) {
      // Show the last known value immediately, but NEVER trust it as final.
      // A background request always revalidates it.
      if (!p) request(path, { ...options, cache: 'no-store' }).catch(() => {})
      return c.data
    }
    if (p) return p
  }
  const token = getToken()
  const headers = { 'Content-Type':'application/json', 'X-Maintain-Application':'engineering', ...(options.headers || {}) }
  if (token) headers.Authorization = 'Bearer ' + token
  const controller = new AbortController()
  const timeoutMs = isRemoteForecast ? 75000 : 20000
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs)
  const base = await getApiBaseUrl()
  let fp
  if (isRemoteForecast) {
    fp = runRemoteChronosForecast(path, base, headers, controller.signal).catch(err => { if (err?.name === 'AbortError' || controller.signal.aborted) throw new Error(`Chronos inference timed out after ${timeoutMs / 1000}s`); throw err }).finally(() => window.clearTimeout(timeout))
  } else {
    fp = fetch(base + path, { ...options, headers, signal:controller.signal }).catch(err => { if (err?.name === 'AbortError' || controller.signal.aborted) throw new Error(`Request timed out after 20s: ${method} ${path}`); throw err }).finally(() => window.clearTimeout(timeout)).then(async res => {
      if (res.status === 401) { setToken(null); if (unauthorizedHandler) unauthorizedHandler() }
      if (isNotFoundResponse(res) && isGet && isPredictionPath(path)) {
        const compatibility = await predictionCompatibility(path, base, headers, controller.signal)
        if (compatibility) return compatibility
        if (path.includes('/forecast?')) {
          const match = path.match(/^\/api\/predictions\/machines\/([^/]+)\/forecast\?(.*)$/)
          if (match) {
            const params = new URLSearchParams(match[2]); const compatibilityModel = params.get('model') === 'timer' ? 'timer' : 'chronos2'
            return await runRemoteChronosForecast(`/api/analytics/machines/${match[1]}/forecast?${params.toString().replace(/(^|&)model=[^&]*/, '$1model=' + compatibilityModel)}`, base, headers, controller.signal)
          }
        }
      }
      if (!res.ok) { const body = await res.text(); throw new Error(res.status + ' ' + res.statusText + ': ' + body) }
      const ct = res.headers.get('content-type') || ''
      return ct.includes('application/json') ? await res.json() : await res.text()
    })
  }
  if (cacheableGet) getInFlight.set(path, fp)
  try { const data = await fp; if (cacheableGet) getCache.set(path, { time:Date.now(), data }); return data }
  finally { if (cacheableGet && getInFlight.get(path) === fp) getInFlight.delete(path) }
}
export const api = {
  get: (p, options = {}) => request(p, options),
  post: async (p,b) => { const r = await request(p,{method:'POST',body:JSON.stringify(b),cache:'no-store'}); clearApiCache(); return r },
  patch: async (p,b) => { const r = await request(p,{method:'PATCH',body:JSON.stringify(b),cache:'no-store'}); clearApiCache(); return r },
  put: async (p,b) => { const r = await request(p,{method:'PUT',body:JSON.stringify(b),cache:'no-store'}); clearApiCache(); return r },
  del: async p => { const r = await request(p,{method:'DELETE',cache:'no-store'}); clearApiCache(); return r },
}; export default api
