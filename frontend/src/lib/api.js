// Thin client for the CodeU backend (see docs/api.md).
// In dev, Vite proxies /api to the FastAPI server, so the default base is ''.
const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '')

export class ApiError extends Error {
  constructor(message, status) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

const FRIENDLY_ERRORS = {
  404: 'We could not find that. It may have been removed.',
  422: 'Some of the details look off. Check them and try again.',
  502: 'The AI tutor could not answer just now. Try again in a moment.',
  503: 'The course knowledge base is unreachable right now. Try again shortly.',
}

async function send(path, { method = 'GET', body, form, signal } = {}) {
  let response
  try {
    response = await fetch(`${API_BASE}/api/v1${path}`, {
      method,
      signal,
      // FormData sets its own multipart Content-Type with the boundary.
      headers: body ? { 'Content-Type': 'application/json' } : undefined,
      body: form ?? (body ? JSON.stringify(body) : undefined),
    })
  } catch (error) {
    if (error.name === 'AbortError') throw error
    throw new ApiError('Cannot reach the CodeU server. Check that the backend is running.', 0)
  }

  if (!response.ok) {
    let detail = null
    try {
      detail = (await response.json()).detail
    } catch {
      // Non-JSON error body: use the generic message.
    }
    // Voice endpoints return learner-safe details; prefer them over generic text.
    const message = path.startsWith('/voice/') && typeof detail === 'string' ? detail : null
    throw new ApiError(message ?? FRIENDLY_ERRORS[response.status] ?? 'Something went wrong on our side.', response.status)
  }
  return response
}

const request = async (path, options) => (await send(path, options)).json()

const enc = encodeURIComponent

export const api = {
  listCourses: (options) => request('/courses?status=complete', options),
  getCourse: (courseId, options) => request(`/courses/${enc(courseId)}`, options),
  getLesson: (courseId, stepId, options) =>
    request(`/courses/${enc(courseId)}/lessons/${enc(stepId)}`, options),
  suggest: (profile, maxSuggestions = 6) =>
    request('/onboarding/suggestions', {
      method: 'POST',
      body: { profile, max_suggestions: maxSuggestions },
    }),
  generateCourse: (courseTopic) =>
    request('/courses/generate', { method: 'POST', body: { course_topic: courseTopic } }),
  getJob: (jobId, options) => request(`/courses/jobs/${enc(jobId)}`, options),
  raiseHand: ({ courseTitle, stepId, question }) =>
    request('/tutor/raise-hand', {
      method: 'POST',
      body: { course_title: courseTitle, step_id: stepId, student_question: question },
    }),
  // Speech-to-text (Groq Whisper). Resolves to { text, language, duration_seconds }.
  transcribe: (audioBlob, { language, signal } = {}) => {
    const form = new FormData()
    const ext = audioBlob.type.includes('mp4') ? 'mp4' : audioBlob.type.includes('ogg') ? 'ogg' : 'webm'
    form.append('audio', audioBlob, `question.${ext}`)
    if (language) form.append('language', language)
    return request('/voice/transcribe', { method: 'POST', form, signal })
  },
  // Text-to-speech (edge-tts). Resolves to an MP3 Blob.
  speak: async (text, { signal } = {}) =>
    (await send('/voice/speak', { method: 'POST', body: { text }, signal })).blob(),
}
