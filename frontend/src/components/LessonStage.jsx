import { lazy, Suspense, useEffect, useRef, useState } from 'react'
import { stripSavedHeader } from '../lib/lessonText'

// The Markdown renderer is the heaviest dependency; load it with the first lesson.
const LessonContent = lazy(() => import('./LessonContent'))

function ArrowIcon({ flip = false }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      aria-hidden="true"
      className={`h-4 w-4 ${flip ? 'rotate-180' : ''}`}
    >
      <path d="M5 12h14m-6-6 6 6-6 6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

function StageMessage({ title, body, action }) {
  return (
    <div className="grid h-full place-items-center px-6 text-center">
      <div className="max-w-sm">
        <p className="text-[17px] font-semibold text-white">{title}</p>
        {body && <p className="mt-2 text-[14px] leading-6 text-slate-400">{body}</p>}
        {action}
      </div>
    </div>
  )
}

function LoadingLines() {
  return (
    <div className="mx-auto w-full max-w-[72ch] animate-pulse space-y-4 px-6 pt-12" aria-label="Loading lesson">
      <div className="h-8 w-2/3 rounded-lg bg-white/[0.06]" />
      {[100, 94, 97, 70, 0, 92, 88, 60].map((w, i) =>
        w ? <div key={i} className="h-4 rounded bg-white/[0.05]" style={{ width: `${w}%` }} /> : <div key={i} className="h-3" />,
      )}
    </div>
  )
}

// Movie-style subtitles inside the stage's bottom edge.
function Captions({ caption, captionKey, status }) {
  const [hidden, setHidden] = useState(false)
  if (!caption) return null

  return (
    <div className="pointer-events-none absolute inset-x-0 bottom-0 z-20 bg-gradient-to-t from-black/75 via-black/40 to-transparent px-4 pb-20 pt-20 lg:pb-6 lg:pl-[200px] lg:pr-10 xl:pl-[250px]">
      <div className="pointer-events-auto mx-auto flex max-w-3xl flex-col items-center gap-2">
        {!hidden && (
          <p
            key={captionKey}
            dir="auto"
            aria-live="polite"
            className="caption-in text-shadow-cinema rounded-lg bg-black/55 px-4 py-2 text-center text-[17px] font-medium leading-8 text-white sm:text-[19px]"
          >
            {caption}
          </p>
        )}
        <button
          type="button"
          onClick={() => setHidden((value) => !value)}
          aria-pressed={!hidden}
          className="rounded-md border border-white/15 bg-black/40 px-2 py-0.5 font-mono text-[10px] font-bold text-slate-300 transition hover:text-white"
        >
          {hidden ? 'CC off' : 'CC'}
          <span className="sr-only"> captions, professor is {status}</span>
        </button>
      </div>
    </div>
  )
}

export default function LessonStage({ lesson, loading, error, onRetry, onNavigate, onComplete, isDone, tutor }) {
  const scrollRef = useRef(null)

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: 0 })
  }, [lesson?.step_id])

  let body
  if (error) {
    body = (
      <StageMessage
        title="This lesson did not load"
        body={error}
        action={
          <button
            type="button"
            onClick={onRetry}
            className="mt-5 rounded-xl bg-ember-500 px-5 py-2.5 text-[14px] font-bold text-white transition hover:bg-ember-400"
          >
            Try again
          </button>
        }
      />
    )
  } else if (loading || !lesson) {
    body = <LoadingLines />
  } else {
    const markdown = stripSavedHeader(lesson.content_markdown, lesson.section_title, lesson.title)
    body = (
      <article className="mx-auto w-full max-w-[74ch] px-6 pb-56 pt-10 sm:px-10 lg:pt-12">
        <Suspense fallback={<LoadingLines />}>
          <LessonContent markdown={markdown} />
        </Suspense>

        <nav
          aria-label="Lesson navigation"
          className="mt-14 flex flex-wrap items-center justify-between gap-3 border-t border-white/[0.08] pt-6"
        >
          <button
            type="button"
            disabled={!lesson.previous_step_id}
            onClick={() => onNavigate(lesson.previous_step_id)}
            className="flex items-center gap-2 rounded-xl px-4 py-2.5 text-[14px] font-semibold text-slate-300 transition hover:bg-white/[0.05] hover:text-white disabled:invisible"
          >
            <ArrowIcon flip />
            Previous
          </button>
          <button
            type="button"
            onClick={onComplete}
            className="flex items-center gap-2 rounded-xl bg-ember-500 px-5 py-2.5 text-[14px] font-bold text-white transition hover:bg-ember-400"
          >
            {lesson.next_step_id ? (isDone ? 'Next lesson' : 'Complete and continue') : isDone ? 'Course finished' : 'Finish course'}
            {lesson.next_step_id && <ArrowIcon />}
          </button>
        </nav>
      </article>
    )
  }

  return (
    <section
      aria-label="Lesson"
      className="relative h-[calc(100vh-88px)] min-h-[480px] overflow-hidden rounded-2xl lg:h-full lg:min-h-0 border border-white/[0.07] bg-abyss-850"
    >
      {/* Left inset keeps lesson text clear of the floating professor until the
          screen is wide enough for the centered column to clear it alone. */}
      <div ref={scrollRef} className="scrollbar-thin h-full overflow-y-auto lg:pl-[150px] xl:pl-[190px] 2xl:pl-0">
        {body}
      </div>
      <Captions caption={tutor.caption} captionKey={tutor.captionKey} status={tutor.status} />
    </section>
  )
}
