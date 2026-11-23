import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api } from '../lib/api'
import { loadJSON, saveJSON } from '../lib/storage'
import { useTutor } from '../lib/useTutor'
import CurriculumSidebar from './CurriculumSidebar'
import LessonStage from './LessonStage'
import Professor from './Professor'

const firstAvailableStep = (course) =>
  course?.sections.flatMap((s) => s.steps).find((step) => step.available)?.step_id ?? null

// Loads data whenever `key` changes. While a new key loads, the previous data
// stays available and `loading` is derived as true.
function useAsync(key, loader) {
  const loaderRef = useRef(loader)
  useEffect(() => {
    loaderRef.current = loader
  })
  const [attempt, setAttempt] = useState(0)
  const requestKey = `${key}#${attempt}`
  const [result, setResult] = useState({ key: null, data: null, error: null })

  useEffect(() => {
    const controller = new AbortController()
    loaderRef.current(controller.signal)
      .then((data) => setResult({ key: requestKey, data, error: null }))
      .catch((error) => {
        if (error.name !== 'AbortError') setResult({ key: requestKey, data: null, error: error.message })
      })
    return () => controller.abort()
  }, [requestKey])

  const loading = result.key !== requestKey
  return {
    data: result.data,
    error: loading ? null : result.error,
    loading,
    retry: () => setAttempt((n) => n + 1),
  }
}

function LessonWithProfessor({ course, stepId, lessonState, onNavigate, onComplete, isDone }) {
  // useTutor resets itself when the lesson changes; the avatar stays mounted.
  const tutor = useTutor({ courseTitle: course?.title, stepId })
  return (
    <>
      <LessonStage
        lesson={lessonState.data}
        loading={lessonState.loading}
        error={lessonState.error}
        onRetry={lessonState.retry}
        onNavigate={onNavigate}
        onComplete={onComplete}
        isDone={isDone}
        tutor={tutor}
      />
      <Professor tutor={tutor} disabled={!lessonState.data} />
    </>
  )
}

export default function Classroom({ courseId, onCourseChange, onFindCourses }) {
  const courses = useAsync('courses', (signal) => api.listCourses({ signal }))
  const courseList = useMemo(() => courses.data ?? [], [courses.data])
  const activeCourseId =
    courseList.find((c) => c.course_id === courseId)?.course_id ?? courseList[0]?.course_id ?? null

  const course = useAsync(activeCourseId, (signal) =>
    activeCourseId ? api.getCourse(activeCourseId, { signal }) : Promise.resolve(null),
  )

  const [stepByCourse, setStepByCourse] = useState(() => loadJSON('steps', {}))
  const [completedByCourse, setCompletedByCourse] = useState(() => loadJSON('completed', {}))

  const courseDetail = course.data?.course_id === activeCourseId ? course.data : null
  const savedStep = stepByCourse[activeCourseId]
  const stepExists = courseDetail?.sections.some((s) => s.steps.some((st) => st.step_id === savedStep && st.available))
  const stepId = stepExists ? savedStep : firstAvailableStep(courseDetail)

  const lesson = useAsync(`${activeCourseId}/${stepId}`, (signal) =>
    activeCourseId && stepId ? api.getLesson(activeCourseId, stepId, { signal }) : Promise.resolve(null),
  )

  // Server progress is the source of truth; the local copy keeps the UI
  // instant (optimistic) and covers older sessions saved only in the browser.
  const progress = useAsync(`progress:${activeCourseId}`, (signal) =>
    activeCourseId ? api.getProgress(activeCourseId, { signal }).catch(() => null) : Promise.resolve(null),
  )
  const serverDone = progress.data?.course_id === activeCourseId ? progress.data.completed_steps : null
  const completed = useMemo(
    () => new Set([...(serverDone ?? []), ...(completedByCourse[activeCourseId] ?? [])]),
    [serverDone, completedByCourse, activeCourseId],
  )

  // One-time upload of lessons completed before progress lived on the server.
  const migratedRef = useRef(new Set())
  useEffect(() => {
    if (!serverDone || migratedRef.current.has(activeCourseId)) return
    migratedRef.current.add(activeCourseId)
    const localOnly = (completedByCourse[activeCourseId] ?? []).filter((step) => !serverDone.includes(step))
    localOnly.forEach((step) => api.completeLesson(activeCourseId, step).catch(() => {}))
  }, [serverDone, activeCourseId, completedByCourse])

  useEffect(() => {
    if (activeCourseId && activeCourseId !== courseId) onCourseChange(activeCourseId)
  }, [activeCourseId, courseId, onCourseChange])

  const selectLesson = useCallback(
    (nextStep) => {
      if (!activeCourseId || !nextStep) return
      setStepByCourse((prev) => {
        const next = { ...prev, [activeCourseId]: nextStep }
        saveJSON('steps', next)
        return next
      })
    },
    [activeCourseId],
  )

  const completeLesson = () => {
    const current = lesson.data
    if (!current) return
    setCompletedByCourse((prev) => {
      const set = new Set(prev[activeCourseId] ?? [])
      set.add(current.step_id)
      const next = { ...prev, [activeCourseId]: [...set] }
      saveJSON('completed', next)
      return next
    })
    // Saved locally first; the server call can fail without losing the tick.
    api.completeLesson(activeCourseId, current.step_id).catch(() => {})
    if (current.next_step_id) selectLesson(current.next_step_id)
  }

  if (!courses.loading && !courses.error && courseList.length === 0) {
    return (
      <div className="grid min-h-[calc(100vh-64px)] place-items-center px-6 text-center">
        <div className="max-w-md">
          <h1 className="text-2xl font-bold text-white">No finished courses yet</h1>
          <p className="mt-3 text-[15px] leading-7 text-slate-400">
            Tell us what you want to learn and we&apos;ll generate your first course.
          </p>
          <button
            type="button"
            onClick={onFindCourses}
            className="mt-6 rounded-xl bg-ember-500 px-6 py-3 text-[15px] font-bold text-white transition hover:bg-ember-400"
          >
            Find a course
          </button>
        </div>
      </div>
    )
  }

  const stageError = courses.error || course.error || lesson.error
  const stageRetry = courses.error ? courses.retry : course.error ? course.retry : lesson.retry

  return (
    <main
      id="classroom"
      className="grid flex-1 grid-cols-1 lg:h-[calc(100vh-64px)] lg:flex-none lg:grid-cols-[minmax(0,1fr)_360px] lg:grid-rows-[minmax(0,1fr)] xl:grid-cols-[minmax(0,1fr)_400px]"
    >
      <div className="min-h-0 p-3 sm:p-4 lg:p-5">
        <LessonWithProfessor
          course={courseDetail}
          stepId={stepId}
          lessonState={{ ...lesson, error: stageError, retry: stageRetry }}
          onNavigate={selectLesson}
          onComplete={completeLesson}
          isDone={lesson.data ? completed.has(lesson.data.step_id) : false}
        />
      </div>

      <div className="min-h-0 border-t border-white/[0.07] lg:border-l lg:border-t-0">
        {courseDetail ? (
          <CurriculumSidebar
            key={activeCourseId}
            courses={courseList}
            course={courseDetail}
            selectedStepId={stepId}
            completed={completed}
            onSelectCourse={onCourseChange}
            onSelectLesson={selectLesson}
          />
        ) : (
          <div className="h-full animate-pulse bg-abyss-900 p-5" aria-label="Loading course content">
            <div className="h-5 w-40 rounded bg-white/[0.06]" />
            <div className="mt-4 h-10 rounded-lg bg-white/[0.05]" />
          </div>
        )}
      </div>
    </main>
  )
}
