import { useState } from 'react'

function ChevronIcon({ open }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      aria-hidden="true"
      className={`h-4 w-4 shrink-0 transition-transform duration-200 ${open ? 'rotate-180' : ''}`}
    >
      <path d="m6 9 6 6 6-6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

function CheckIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" aria-hidden="true" className="h-3 w-3">
      <path d="m5 12 4.5 4.5L19 7" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

function PlayIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" className="h-2.5 w-2.5">
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
      aria-hidden="true"
      className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400"
    >
      <path d="m6 9 6 6 6-6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

const formatMinutes = (mins) => (mins >= 60 ? `${Math.floor(mins / 60)}h ${mins % 60}m` : `${mins} min`)

function LessonMarker({ active, done }) {
  if (active) {
    return (
      <span className="grid h-5 w-5 shrink-0 place-items-center rounded-full bg-ember-500 text-white">
        <PlayIcon />
      </span>
    )
  }
  if (done) {
    return (
      <span className="grid h-5 w-5 shrink-0 place-items-center rounded-full bg-emerald-500/90 text-abyss-950">
        <CheckIcon />
      </span>
    )
  }
  return <span className="h-5 w-5 shrink-0 rounded-full border-2 border-slate-600" />
}

export default function CurriculumSidebar({
  courses,
  course,
  selectedStepId,
  completed,
  onSelectCourse,
  onSelectLesson,
}) {
  const sections = course?.sections ?? []
  const allSteps = sections.flatMap((section) => section.steps)
  const doneCount = allSteps.filter((step) => completed.has(step.step_id)).length
  const progress = allSteps.length ? Math.round((doneCount / allSteps.length) * 100) : 0
  const activeSectionId = sections.find((section) =>
    section.steps.some((step) => step.step_id === selectedStepId),
  )?.section_id

  // Opened sections are remembered; the active one is always open.
  const [opened, setOpened] = useState(() => new Set())
  const [closed, setClosed] = useState(() => new Set())
  const isOpen = (id) => (id === activeSectionId ? !closed.has(id) : opened.has(id))
  const toggle = (id) => {
    const flip = (set) => {
      const next = new Set(set)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    }
    if (id === activeSectionId) setClosed(flip)
    else setOpened(flip)
  }

  return (
    <aside aria-label="Course content" className="flex h-full min-h-0 flex-col bg-abyss-900">
      <div className="shrink-0 border-b border-white/[0.07] px-5 pb-4 pt-5">
        <h2 className="text-[15px] font-bold text-white">Course content</h2>

        {courses.length > 1 && (
          <label className="relative mt-3 block">
            <span className="sr-only">Switch course</span>
            <select
              value={course?.course_id ?? ''}
              onChange={(event) => onSelectCourse(event.target.value)}
              className="w-full appearance-none truncate rounded-lg border border-white/[0.09] bg-abyss-850 py-2.5 pl-3 pr-9 text-[13px] font-semibold text-slate-100 transition hover:border-white/20"
            >
              {courses.map((item) => (
                <option key={item.course_id} value={item.course_id}>
                  {item.title}
                </option>
              ))}
            </select>
            <SelectChevron />
          </label>
        )}

        {courses.length <= 1 && course && (
          <p className="mt-1 text-[13px] leading-5 text-slate-400">{course.title}</p>
        )}

        <div className="mt-4 flex items-center justify-between text-[12px] text-slate-400">
          <span>
            {doneCount} of {allSteps.length} lessons done
          </span>
          <span className="font-semibold tabular-nums text-slate-200">{progress}%</span>
        </div>
        <div
          className="mt-2 h-1.5 overflow-hidden rounded-full bg-white/[0.07]"
          role="progressbar"
          aria-valuenow={progress}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label="Course progress"
        >
          <div className="h-full rounded-full bg-emerald-400 transition-[width] duration-500" style={{ width: `${progress}%` }} />
        </div>
      </div>

      <div className="scrollbar-thin min-h-0 flex-1 overflow-y-auto">
        {sections.map((section, sectionIndex) => {
          const open = isOpen(section.section_id)
          const sectionDone = section.steps.filter((step) => completed.has(step.step_id)).length
          const minutes = section.steps.reduce((sum, step) => sum + step.duration_mins, 0)

          return (
            <section key={section.section_id} className="border-b border-white/[0.07]">
              <button
                type="button"
                onClick={() => toggle(section.section_id)}
                aria-expanded={open}
                aria-controls={`section-${section.section_id}`}
                className="flex w-full items-start gap-3 bg-abyss-850 px-5 py-3.5 text-left transition hover:bg-abyss-800"
              >
                <span className="min-w-0 flex-1">
                  <span className="block text-[13.5px] font-bold leading-5 text-slate-100">
                    Section {sectionIndex + 1}: {section.title}
                  </span>
                  <span className="mt-1 block text-[12px] tabular-nums text-slate-400">
                    {sectionDone} / {section.steps.length} | {formatMinutes(minutes)}
                  </span>
                </span>
                <span className="mt-0.5 text-slate-400">
                  <ChevronIcon open={open} />
                </span>
              </button>

              {open && (
                <ul id={`section-${section.section_id}`}>
                  {section.steps.map((step, stepIndex) => {
                    const active = step.step_id === selectedStepId
                    const done = completed.has(step.step_id)
                    return (
                      <li key={step.step_id}>
                        <button
                          type="button"
                          disabled={!step.available}
                          onClick={() => onSelectLesson(step.step_id)}
                          aria-current={active ? 'step' : undefined}
                          className={`flex w-full items-start gap-3 px-5 py-3 text-left transition disabled:cursor-not-allowed disabled:opacity-50 ${
                            active ? 'bg-ember-500/[0.12]' : 'hover:bg-white/[0.04]'
                          }`}
                        >
                          <LessonMarker active={active} done={done} />
                          <span className="min-w-0 flex-1">
                            <span
                              className={`block text-[13px] leading-5 ${
                                active ? 'font-semibold text-white' : 'text-slate-300'
                              }`}
                            >
                              {stepIndex + 1}. {step.title}
                            </span>
                            <span className="mt-1 block text-[11.5px] tabular-nums text-slate-500">
                              {step.available ? `${step.duration_mins} min` : 'Not generated yet'}
                            </span>
                          </span>
                        </button>
                      </li>
                    )
                  })}
                </ul>
              )}
            </section>
          )
        })}
      </div>
    </aside>
  )
}
