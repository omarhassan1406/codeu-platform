import { useEffect, useState } from 'react'
import { api } from '../../lib/api'
import RiveAvatar from '../RiveAvatar'

const POLL_MS = 3000
const MAX_POLL_FAILURES = 5

function headline(job) {
  if (!job || job.status === 'queued') return 'Getting started…'
  if (job.status === 'failed') return 'This course could not be finished'
  if (job.status === 'complete') return 'Your course is ready!'
  if (!job.total_steps) return 'Planning the course outline…'
  return `Writing lesson ${Math.min(job.completed_steps + 1, job.total_steps)} of ${job.total_steps}`
}

export default function GenerationProgress({ jobId, topic, onOpen, onBack }) {
  const [job, setJob] = useState(null)
  const [pollError, setPollError] = useState(null)

  useEffect(() => {
    let cancelled = false
    let timer = 0
    let failures = 0

    const poll = async () => {
      try {
        const next = await api.getJob(jobId)
        if (cancelled) return
        failures = 0
        setPollError(null)
        setJob(next)
        if (next.status === 'complete' || next.status === 'failed') return
      } catch (error) {
        if (cancelled) return
        failures += 1
        // A 404 means the server restarted and forgot the job.
        if (error.status === 404 || failures >= MAX_POLL_FAILURES) {
          setPollError(
            error.status === 404
              ? 'The server lost track of this job (it may have restarted). Check the catalog or try again.'
              : error.message,
          )
          return
        }
      }
      timer = window.setTimeout(poll, POLL_MS)
    }

    poll()
    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [jobId])

  const done = job?.status === 'complete'
  const failed = job?.status === 'failed' || Boolean(pollError)
  const percent = done ? 100 : job?.total_steps ? Math.round((job.completed_steps / job.total_steps) * 100) : 4
  const avatarStatus = done ? 'explaining' : failed ? 'idle' : 'thinking'

  return (
    <div className="step-in mx-auto flex w-full max-w-xl flex-col items-center px-6 pb-16 pt-10 text-center sm:pt-16">
      <RiveAvatar status={avatarStatus} className="h-[220px] w-[176px]" />
      <h1 className="mt-4 text-[24px] font-bold leading-8 text-white" aria-live="polite">
        {pollError ? 'Lost contact with the generator' : headline(job)}
      </h1>
      <p dir="auto" className="mt-2 text-[15px] text-slate-400">
        {job?.course_title ?? topic}
      </p>

      {!failed && (
        <div className="mt-8 w-full">
          <div
            className="h-4 overflow-hidden rounded-full bg-abyss-800"
            role="progressbar"
            aria-label="Generation progress"
            aria-valuenow={percent}
            aria-valuemin={0}
            aria-valuemax={100}
          >
            <div
              className={`relative h-full rounded-full transition-[width] duration-700 ease-out ${done ? 'bg-emerald-400' : 'bg-ember-500'}`}
              style={{ width: `${percent}%` }}
            >
              <span className="absolute inset-x-2 top-1 h-1 rounded-full bg-white/30" />
            </div>
          </div>
          {!done && (
            <p className="mt-3 text-[13.5px] text-slate-500">
              Every lesson is checked for completeness before it’s saved. You can leave this page; the course keeps building.
            </p>
          )}
        </div>
      )}

      {failed && (
        <p role="alert" className="mt-6 rounded-xl bg-red-500/10 px-4 py-3 text-[14px] leading-6 text-red-200">
          {pollError ?? job?.error}
        </p>
      )}

      <div className="mt-8 flex flex-wrap justify-center gap-3">
        {done && job.course_id && (
          <button type="button" onClick={() => onOpen(job.course_id)} className="btn-press text-[15px] uppercase">
            Start learning
          </button>
        )}
        <button
          type="button"
          onClick={() => onBack(done || failed)}
          className="choice px-5 py-3 text-[14px] font-bold"
        >
          {done ? 'Back to suggestions' : failed ? 'Back to suggestions' : 'Browse while I work'}
        </button>
      </div>
    </div>
  )
}
