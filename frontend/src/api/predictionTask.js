const tasks = new Map()
const listeners = new Set()

function notify() {
  for (const listener of listeners) {
    try { listener() } catch {}
  }
}

export function subscribePredictionTasks(listener) {
  listeners.add(listener)
  listener()
  return () => listeners.delete(listener)
}

export function getPredictionTask(key) {
  return tasks.get(key) || null
}

export function startPredictionTask({ key, run }) {
  const existing = tasks.get(key)
  if (existing?.status === 'running') return existing.promise

  const task = {
    key,
    status: 'running',
    startedAt: Date.now(),
    result: null,
    error: null,
    promise: null,
  }
  tasks.set(key, task)
  notify()

  task.promise = Promise.resolve()
    .then(run)
    .then(result => {
      if (tasks.get(key) !== task) return result
      task.status = result?.available ? 'completed' : 'failed'
      task.result = result
      notify()
      return result
    })
    .catch(error => {
      if (tasks.get(key) === task) {
        task.status = 'failed'
        task.error = error?.message || 'Prediction request failed.'
        notify()
      }
      throw error
    })

  return task.promise
}

export function clearPredictionTask(key) {
  if (tasks.delete(key)) notify()
}
