// Per-browser conveniences only (profile, last lesson). Storage can be blocked
// or cleared, so every access is guarded and the app works without it.
const PREFIX = 'codeu:'

export function loadJSON(key, fallback = null) {
  try {
    const raw = window.localStorage.getItem(PREFIX + key)
    return raw ? JSON.parse(raw) : fallback
  } catch {
    return fallback
  }
}

export function saveJSON(key, value) {
  try {
    if (value === null || value === undefined) window.localStorage.removeItem(PREFIX + key)
    else window.localStorage.setItem(PREFIX + key, JSON.stringify(value))
  } catch {
    // Storage unavailable: the session still works, it just will not be remembered.
  }
}
