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

async function request(path, { method = 'GET', body, signal } = {}) {
  let response
  try {
    response = await fetch(`${API_BASE}/api/v1${path}`, {
      method,
      signal,
      headers: body ? { 'Content-Type': 'application/json' } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    })
  } catch (error) {
    if (error.name === 'AbortError') throw error
    throw new ApiError('Cannot reach the CodeU server. Check that the backend is running.', 0)
  }

  if (!response.ok) {
    throw new ApiError(FRIENDLY_ERRORS[response.status] ?? 'Something went wrong on our side.', response.status)
  }
  return response.json()
}

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
}
