import { useState } from 'react'
import { flattenLessons } from '../data/courses'

function ChevronIcon({ open }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      className={`h-3.5 w-3.5 shrink-0 transition-transform duration-200 ${open ? 'rotate-90' : ''}`}
    >
      <path d="m9 5 7 7-7 7" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

function CheckIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" className="h-3 w-3">
      <path d="m5 12 4.5 4.5L19 7" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

function PlayIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className="h-2.5 w-2.5">
      <path d="M8 5.5v13l11-6.5-11-6.5Z" />
    </svg>
  )
}

function SelectChevron() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      className="pointer-events-none absolute right-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-500"
    >
      <path d="m6 9 6 6 6-6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

function LessonStatus({ active, completed, index }) {
  if (active) {
    return (
      <span className="relative grid h-6 w-6 shrink-0 place-items-center rounded-full bg-ember-500/15 text-ember-300 ring-1 ring-ember-500/35">
        <span className="absolute inset-0 rounded-full bg-ember-500/10 status-pulse" />
        <PlayIcon />
      </span>
    )
  }

  if (completed) {
    return (
      <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-emerald-400/10 text-emerald-300 ring-1 ring-emerald-400/20">
        <CheckIcon />
      </span>
    )
  }

  return (
    <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full border border-white/[0.08] font-mono text-[9px] text-slate-500">
      {index}
    </span>
  )
}

export default function CurriculumSidebar({
  courses,
  course,
  selectedLessonId,
  onSelectCourse,
  onSelectLesson,
  className = '',
}) {
  const allLessons = flattenLessons(course)
  const completed = allLessons.filter((lesson) => lesson.completed).length
  const total = allLessons.length
  const progress = total > 0 ? Math.round((completed / total) * 100) : 0
  const activeSection = course.sections.find((section) =>
    section.lessons.some((lesson) => lesson.id === selectedLessonId),
  )
  const [openSections, setOpenSections] = useState(
    () => new Set(activeSection ? [activeSection.id] : []),
  )

  const toggleSection = (sectionId) => {
    setOpenSections((previous) => {
      const next = new Set(previous)
      if (next.has(sectionId)) next.delete(sectionId)
      else next.add(sectionId)
      return next
    })
  }

  return (
    <aside
      id="curriculum"
      aria-label="Course curriculum"
      className={`panel flex flex-col overflow-hidden ${className}`}
    >
      <div className="shrink-0 border-b border-white/[0.06] px-4 pb-4 pt-4">
        <div className="flex items-center justify-between">
          <p className="text-[10px] font-semibold uppercase tracking-[0.24em] text-slate-500">
            Course curriculum
          </p>
          <span className="rounded-full bg-white/[0.05] px-2 py-0.5 text-[9px] font-medium text-slate-400">
            {total} lessons
          </span>
        </div>

        <label className="relative mt-3 block">
          <span className="sr-only">Select a course</span>
          <select
            value={course.id}
            onChange={(event) => onSelectCourse(event.target.value)}
            className="w-full appearance-none rounded-xl border border-white/[0.07] bg-abyss-950/70 px-3 py-2.5 pr-9 text-[12px] font-semibold text-slate-100 outline-none transition focus:border-ember-500/40 focus:ring-2 focus:ring-ember-500/15"
          >
            {courses.map((item) => (
              <option key={item.id} value={item.id}>
                {item.mark} · {item.title}
              </option>
            ))}
          </select>
          <SelectChevron />
        </label>

        <div className="mt-3 flex items-center justify-between text-[10px] font-medium text-slate-500">
          <span>
            {completed} of {total} complete
          </span>
          <span className="font-semibold text-ember-300">{progress}%</span>
        </div>
        <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-white/[0.06]">
          <div
            className="h-full rounded-full bg-gradient-to-r from-ember-500 to-ember-300 transition-all duration-500"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      <div className="scrollbar-thin min-h-0 flex-1 space-y-2 overflow-y-auto p-2.5">
        {course.sections.map((section) => {
          const open = openSections.has(section.id)
          const completedInSection = section.lessons.filter((lesson) => lesson.completed).length

          return (
            <div
              key={section.id}
              className="overflow-hidden rounded-xl border border-white/[0.05] bg-white/[0.015]"
            >
              <button
                type="button"
                onClick={() => toggleSection(section.id)}
                aria-expanded={open}
                aria-controls={`section-${section.id}`}
                className="flex w-full items-center gap-2.5 px-3 py-3 text-left transition hover:bg-white/[0.03]"
              >
                <span className="text-slate-500">
                  <ChevronIcon open={open} />
                </span>
                <span className="min-w-0 flex-1 truncate text-[12px] font-semibold text-slate-200">
                  {section.title}
                </span>
                <span className="shrink-0 font-mono text-[9px] text-slate-500">
                  {completedInSection}/{section.lessons.length}
                </span>
              </button>

              {open && (
                <ul id={`section-${section.id}`} className="space-y-0.5 border-t border-white/[0.04] p-1.5">
                  {section.lessons.map((lesson, lessonIndex) => {
                    const active = lesson.id === selectedLessonId
                    const statusLabel = active
                      ? 'Now playing'
                      : lesson.completed
                        ? 'Completed'
                        : 'Up next'

                    return (
                      <li key={lesson.id}>
                        <button
                          type="button"
                          onClick={() => onSelectLesson(lesson.id)}
                          aria-current={active ? 'step' : undefined}
                          className={`flex w-full items-start gap-2.5 rounded-lg px-2 py-2 text-left transition ${
                            active
                              ? 'bg-ember-500/[0.08] ring-1 ring-inset ring-ember-500/20'
                              : 'hover:bg-white/[0.04]'
                          }`}
                        >
                          <LessonStatus
                            active={active}
                            completed={lesson.completed}
                            index={lessonIndex + 1}
                          />

                          <span className="min-w-0 flex-1">
                            <span
                              className={`block truncate text-[12px] leading-5 ${
                                active
                                  ? 'font-semibold text-ember-100'
                                  : lesson.completed
                                    ? 'text-slate-300'
                                    : 'text-slate-400'
                              }`}
                            >
                              {lesson.title}
                            </span>
                            <span
                              className={`mt-0.5 block text-[8.5px] font-semibold uppercase tracking-[0.16em] ${
                                active ? 'text-ember-400/90' : 'text-slate-600'
                              }`}
                            >
                              {statusLabel}
                            </span>
                          </span>

                          <span className="shrink-0 pt-0.5 text-[10px] tabular-nums text-slate-500">
                            {lesson.duration}
                          </span>
                        </button>
                      </li>
                    )
                  })}
                </ul>
              )}
            </div>
          )
        })}
      </div>

      <div id="progress" className="shrink-0 border-t border-white/[0.06] p-3">
        <div className="rounded-xl border border-white/[0.06] bg-abyss-950/50 p-3.5">
          <div className="flex items-center justify-between">
            <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-slate-500">
              Daily goal
            </p>
            <span className="text-[10px] font-semibold text-ember-300">3 / 5 lessons</span>
          </div>

          <div className="mt-2.5 h-1.5 overflow-hidden rounded-full bg-white/[0.06]">
            <div className="h-full w-3/5 rounded-full bg-gradient-to-r from-ember-500 to-ember-300" />
          </div>

          <p className="mt-2.5 text-[10px] leading-5 text-slate-500">
            Two more lessons keep your 7-day streak alive.
          </p>
        </div>
      </div>
    </aside>
  )
}
