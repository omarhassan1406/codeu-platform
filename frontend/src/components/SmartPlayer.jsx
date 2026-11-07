import { useEffect, useMemo, useState } from 'react'
import CodeViewer from './CodeViewer'
import SubtitlesBox from './SubtitlesBox'

const SCENE_DURATION = 12000

const FALLBACK_SLIDE = {
  kicker: 'Lesson overview',
  title: 'Content is being prepared.',
  points: ['The professor is assembling this step.', 'The code walkthrough follows shortly.'],
  aside: 'More coming up.',
}

function PlayIcon({ className = 'h-3.5 w-3.5' }) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className={className} aria-hidden="true">
      <path d="M8 5.5v13l11-6.5-11-6.5Z" />
    </svg>
  )
}

function PauseIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className="h-3.5 w-3.5" aria-hidden="true">
      <rect x="7" y="5" width="3.5" height="14" rx="1.2" />
      <rect x="13.5" y="5" width="3.5" height="14" rx="1.2" />
    </svg>
  )
}

function ReplayIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-3.5 w-3.5" aria-hidden="true">
      <path d="M4 12a8 8 0 1 0 2.4-5.7M4 4v4.5h4.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

function buildScenes(lesson) {
  const slides = lesson.slides?.length ? lesson.slides : [FALLBACK_SLIDE]
  const scenes = []

  slides.forEach((slide, index) => {
    scenes.push({
      id: `slide-${index}`,
      type: 'slide',
      label: slide.kicker,
      slide,
    })

    if (index === 0) {
      scenes.push({ id: 'code', type: 'code', label: 'Live code walkthrough' })
    }
  })

  return scenes
}

function SlideScene({ lesson, slide, sceneNumber, totalScenes }) {
  return (
    <div className="scrollbar-thin relative h-full overflow-y-auto bg-[#0e1016]">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_14%_0%,rgba(255,87,34,0.13),transparent_46%),radial-gradient(circle_at_92%_96%,rgba(120,140,175,0.08),transparent_48%)]"
      />

      <div className="relative flex min-h-full flex-col justify-start px-5 pb-40 pt-7 sm:px-8 sm:pb-44 sm:pt-8 lg:px-12 lg:pt-10">
        <div className="mx-auto w-full max-w-5xl">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="rounded-full border border-ember-500/20 bg-ember-500/[0.08] px-3 py-1 text-[9px] font-semibold uppercase tracking-[0.18em] text-ember-300">
              {slide.kicker}
            </span>
            <span className="font-mono text-[9px] uppercase tracking-[0.14em] text-slate-500">
              Scene {sceneNumber} of {totalScenes}
            </span>
          </div>

          <div className="mt-5 grid gap-6 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,0.8fr)] lg:items-center lg:gap-10">
            <div>
              <p className="text-[9px] font-semibold uppercase tracking-[0.26em] text-slate-500">
                {lesson.module}
              </p>
              <h2 className="mt-2 text-[26px] font-bold leading-[1.12] tracking-tight text-white sm:text-4xl lg:text-[43px]">
                {slide.title}
              </h2>

              <ul className="mt-5 space-y-3">
                {slide.points.map((point, index) => (
                  <li key={point} className="flex gap-3 text-[13px] leading-6 text-slate-300 sm:text-[14.5px] sm:leading-7">
                    <span className="mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-md bg-ember-500/10 font-mono text-[9px] font-bold text-ember-300 ring-1 ring-ember-500/20">
                      {String(index + 1).padStart(2, '0')}
                    </span>
                    <span>{point}</span>
                  </li>
                ))}
              </ul>
            </div>

            <aside className="relative overflow-hidden rounded-2xl border border-white/[0.08] bg-abyss-900/80 p-5 shadow-[0_24px_60px_-35px_rgba(0,0,0,0.9)]">
              <div className="absolute inset-x-6 top-0 h-px bg-gradient-to-r from-transparent via-ember-500/50 to-transparent" />

              <p className="text-[9px] font-semibold uppercase tracking-[0.2em] text-slate-500">
                Key idea
              </p>
              <p className="mt-3 font-mono text-[13px] leading-6 text-ember-200">{slide.aside}</p>

              <div className="mt-5 flex items-center gap-2 border-t border-white/[0.06] pt-3 text-[9px] text-slate-500">
                <span className="status-pulse h-1.5 w-1.5 rounded-full bg-ember-400" />
                Professor notes · synced with captions
              </div>
            </aside>
          </div>
        </div>
      </div>
    </div>
  )
}

export default function SmartPlayer({ lesson, courseTitle, status }) {
  const scenes = useMemo(() => buildScenes(lesson), [lesson])
  const [sceneIndex, setSceneIndex] = useState(0)
  const [playing, setPlaying] = useState(true)

  const safeIndex = Math.min(sceneIndex, scenes.length - 1)
  const scene = scenes[safeIndex]
  const isLast = safeIndex === scenes.length - 1

  useEffect(() => {
    if (!playing || isLast) return undefined

    const timer = window.setTimeout(() => {
      setSceneIndex((index) => Math.min(index + 1, scenes.length - 1))
    }, SCENE_DURATION)

    return () => window.clearTimeout(timer)
  }, [playing, safeIndex, isLast, scenes.length])

  const selectScene = (index) => {
    setSceneIndex(index)
    setPlaying(true)
  }

  const handlePlayback = () => {
    if (isLast) {
      setSceneIndex(0)
      setPlaying(true)
      return
    }
    setPlaying((value) => !value)
  }

  return (
    <section
      className="panel flex h-[clamp(480px,calc(100vh-124px),860px)] min-h-0 flex-col overflow-hidden bg-abyss-950/70 lg:h-[clamp(480px,calc(100vh-190px),840px)]"
      aria-label="AI smart lesson player"
    >
      <div className="relative z-20 flex shrink-0 items-center justify-between gap-3 border-b border-white/[0.07] bg-abyss-950/55 px-3.5 py-3 backdrop-blur-xl sm:px-5">
        <div className="flex min-w-0 items-center gap-2.5">
          <span className="hidden h-9 w-9 shrink-0 place-items-center rounded-xl bg-gradient-to-br from-ember-400 via-ember-500 to-ember-600 shadow-[0_10px_26px_-12px_rgba(255,87,34,0.85)] sm:grid">
            <PlayIcon className="h-3 w-3 text-white" />
          </span>
          <div className="min-w-0">
            <p className="truncate text-[8.5px] font-semibold uppercase tracking-[0.24em] text-ember-300/90">
              {courseTitle}
            </p>
            <h1 className="truncate text-[13.5px] font-semibold text-white sm:text-[15px]">
              {lesson.title}
            </h1>
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-1.5 sm:gap-2">
          <span className="hidden items-center gap-1.5 rounded-full border border-white/[0.07] bg-white/[0.03] px-2.5 py-1 text-[9px] font-semibold uppercase tracking-[0.14em] text-slate-400 md:flex">
            <span className="status-pulse h-1.5 w-1.5 rounded-full bg-ember-400" />
            AI smart sequence
          </span>
          <span className="hidden rounded-md border border-white/[0.06] bg-white/[0.02] px-2 py-1 font-mono text-[9px] text-slate-500 lg:block">
            {lesson.duration}
          </span>
          <span className="font-mono text-[9px] uppercase tracking-[0.12em] text-slate-500">
            {safeIndex + 1} / {scenes.length}
          </span>
          <button
            type="button"
            onClick={handlePlayback}
            aria-label={
              isLast
                ? 'Replay smart sequence'
                : playing
                  ? 'Pause smart sequence'
                  : 'Play smart sequence'
            }
            className="grid h-8 w-8 place-items-center rounded-lg border border-white/[0.08] bg-white/[0.03] text-slate-300 transition hover:border-ember-500/35 hover:text-ember-300"
          >
            {isLast ? <ReplayIcon /> : playing ? <PauseIcon /> : <PlayIcon />}
          </button>
        </div>
      </div>

      <div className="relative z-20 flex shrink-0 items-center gap-1.5 bg-abyss-950/25 px-3 py-2">
        {scenes.map((item, index) => {
          const active = index === safeIndex
          const complete = index < safeIndex

          return (
            <button
              key={item.id}
              type="button"
              onClick={() => selectScene(index)}
              aria-label={`Go to scene ${index + 1}: ${item.label}`}
              aria-current={active ? 'true' : undefined}
              className="group relative h-1.5 flex-1 overflow-hidden rounded-full bg-white/[0.08] transition hover:bg-white/15"
            >
              <span
                className={`absolute inset-y-0 left-0 rounded-full ${
                  complete ? 'w-full bg-ember-400/40' : active ? 'w-full bg-ember-400' : 'w-0'
                }`}
                style={
                  active && !isLast
                    ? {
                        animation: `scene-progress ${SCENE_DURATION}ms linear forwards`,
                        animationPlayState: playing ? 'running' : 'paused',
                      }
                    : undefined
                }
              />
            </button>
          )
        })}
      </div>

      <div className="relative min-h-0 flex-1">
        <div key={scene.id} className="panel-in absolute inset-0">
          {scene.type === 'code' ? (
            <div className="h-full min-h-0 pb-[150px] sm:pb-[140px]">
              <CodeViewer filename={lesson.filename} language={lesson.language} code={lesson.code} />
            </div>
          ) : (
            <SlideScene
              lesson={lesson}
              slide={scene.slide}
              sceneNumber={safeIndex + 1}
              totalScenes={scenes.length}
            />
          )}
        </div>

        <SubtitlesBox narration={lesson.narration} status={status} />
      </div>
    </section>
  )
}
