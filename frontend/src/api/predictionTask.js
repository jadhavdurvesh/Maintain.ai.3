const listeners = new Set()
let activeTask = null

function notify() {
  for (const listener of listeners) {
    try { listener(activeTask) } catch {}
  }
}

export function subscribePredictionTask(listener) {
  listeners.add(listener)
  listener(activeTask)
  return () => listeners.delete(listener)
}

export function getPredictionTask() {
  return activeTask
}

export function startPredictionTask({ key, run }) {
  if (activeTask?.status === 'running' && activeTask.key === key) return activeTask.promise

  const task = {
    key,
    status: 'running',
    startedAt: Date.now(),
    result: null,
    error: null,
  }
  activeTask = task
  notify()

  task.promise = Promise.resolve()
    .then(run)
    .then(result => {
      if (activeTask !== task) return result
      task.status = result?.available ? 'completed' : 'failed'
      task.result = result
      notify()
      return result
    })
    .catch(error => {
      if (activeTask === task) {
        task.status = 'failed'
        task.error = error?.message || 'Prediction request failed.'
        notify()
      }
      throw error
    })

  return task.promise
}

export function clearPredictionTask(key) {
  if (!activeTask || (key && activeTask.key !== key)) return
  activeTask = null
  notify()
}
