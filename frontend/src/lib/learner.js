// Anonymous learner id, sent as X-Learner-Id so the backend can keep progress
// and the daily question quota. Real sign-in will replace it later.
const KEY = 'codeu:learner-id'

let memoryId = null

function randomId() {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) return crypto.randomUUID()
  return `l-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`
}

export function getLearnerId() {
  try {
    let id = window.localStorage.getItem(KEY)
    if (!id) {
      id = randomId()
      window.localStorage.setItem(KEY, id)
    }
    return id
  } catch {
    // Storage blocked: keep one id for this page session.
    memoryId ??= randomId()
    return memoryId
  }
}
