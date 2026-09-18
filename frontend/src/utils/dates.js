// Backend timestamps are historically stored as naive UTC datetimes.
// Normalize naive UTC, Z, and explicit-offset timestamps before displaying.
export function parseBackendDate(value) {
  if (!value) return null
  if (value instanceof Date) return value
  const text = String(value)
  const normalized = /(?:Z|[+-]\\d{2}:?\\d{2})$/i.test(text) ? text : text + 'Z'
  const date = new Date(normalized)
  return Number.isNaN(date.getTime()) ? null : date
}

export function formatDateTime(value) {
  const date = parseBackendDate(value)
  return date ? date.toLocaleString() : '—'
}

export function formatDate(value) {
  const date = parseBackendDate(value)
  return date ? date.toLocaleDateString() : '—'
}
