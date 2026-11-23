import { useState } from 'react'
import RiveAvatar from '../RiveAvatar'

const POPULAR_TOPICS = [
  'Python',
  'Web development',
  'JavaScript',
  'Flutter',
  'Data science',
  'Machine learning',
  'SQL & databases',
  'Algorithms',
  'Calculus',
  'UI design',
]

const LEVELS = [
  { id: 'beginner', title: 'I’m new to this', body: 'Start from the basics, one step at a time.' },
  { id: 'intermediate', title: 'I know the basics', body: 'Skip the intro and build real skills.' },
  { id: 'advanced', title: 'I’m experienced', body: 'Go deep on patterns and advanced topics.' },
]

const BACKGROUNDS = ['University student', 'School student', 'Working developer', 'Switching careers', 'Learning for fun']
const GOALS = ['Get a job', 'Pass my course', 'Build a project', 'Level up at work', 'Just curious']

const MAX_INTERESTS = 10

function BackIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" aria-hidden="true" className="h-5 w-5">
      <path d="m15 6-6 6 6 6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

function PlusIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" aria-hidden="true" className="h-4 w-4">
      <path d="M12 5v14M5 12h14" strokeLinecap="round" />
    </svg>
  )
}

// The professor "says" each question, Duolingo-style, from a speech bubble.
// The avatar stays mounted across steps (no Rive reload); only the bubble changes.
function ProfessorSays({ children, stepKey, status = 'talking' }) {
  return (
    <div className="flex items-end gap-3 sm:gap-4">
      <RiveAvatar status={status} className="h-[120px] w-[96px] shrink-0 sm:h-[150px] sm:w-[120px]" />
      <div key={stepKey} className="step-in relative mb-6 rounded-2xl border-2 border-abyss-700 bg-abyss-850 px-4 py-3 sm:px-5">
        <span
          aria-hidden="true"
          className="absolute -left-[9px] bottom-4 h-4 w-4 rotate-45 border-b-2 border-l-2 border-abyss-700 bg-abyss-850"
        />
        <h1 className="relative text-[19px] font-bold leading-7 text-white sm:text-[22px]">{children}</h1>
      </div>
    </div>
  )
}

function ChipToggle({ label, selected, onToggle, disabled }) {
  return (
    <button
      type="button"
      aria-pressed={selected}
      disabled={disabled && !selected}
      onClick={onToggle}
      className="choice px-4 py-2.5 text-[14.5px] font-semibold disabled:cursor-not-allowed disabled:opacity-40"
    >
      {label}
    </button>
  )
}

function InterestsStep({ interests, setInterests }) {
  const [custom, setCustom] = useState('')
  const same = (a, b) => a.toLowerCase() === b.toLowerCase()
  const has = (topic) => interests.some((i) => same(i, topic))
  const full = interests.length >= MAX_INTERESTS

  // Functional updates so rapid taps never work from a stale list.
  const toggle = (topic) =>
    setInterests((prev) =>
      prev.some((i) => same(i, topic))
        ? prev.filter((i) => !same(i, topic))
        : prev.length < MAX_INTERESTS
          ? [...prev, topic]
          : prev,
    )

  const addCustom = (event) => {
    event.preventDefault()
    const topic = custom.replace(/\s+/g, ' ').trim()
    if (topic.length < 2 || topic.length > 100 || has(topic) || full) return
    setInterests((prev) => (prev.some((i) => same(i, topic)) || prev.length >= MAX_INTERESTS ? prev : [...prev, topic]))
    setCustom('')
  }

  const customOnes = interests.filter((i) => !POPULAR_TOPICS.some((t) => t.toLowerCase() === i.toLowerCase()))

  return (
    <>
      <div className="flex flex-wrap gap-2.5">
        {[...POPULAR_TOPICS, ...customOnes].map((topic) => (
          <ChipToggle key={topic} label={topic} selected={has(topic)} onToggle={() => toggle(topic)} disabled={full} />
        ))}
      </div>
      <form onSubmit={addCustom} className="mt-5 flex gap-2">
        <label htmlFor="custom-topic" className="sr-only">
          Add your own topic
        </label>
        <input
          id="custom-topic"
          dir="auto"
          value={custom}
          maxLength={100}
          disabled={full}
          onChange={(e) => setCustom(e.target.value)}
          placeholder="Something else? e.g. Organic chemistry"
          className="min-w-0 flex-1 rounded-xl border-2 border-abyss-700 bg-abyss-900 px-4 py-3 text-[15px] text-white placeholder:text-slate-500 focus:border-ember-400 focus:outline-none disabled:opacity-50"
        />
        <button
          type="submit"
          disabled={custom.trim().length < 2 || full}
          className="choice flex items-center gap-1.5 px-4 text-[14px] font-bold disabled:cursor-not-allowed disabled:opacity-40"
        >
          <PlusIcon />
          Add
        </button>
      </form>
      {full && <p className="mt-2 text-[13px] text-amber-200">That’s the maximum of {MAX_INTERESTS} topics.</p>}
    </>
  )
}

function LevelStep({ level, setLevel }) {
  return (
    <>
      <div role="radiogroup" aria-label="Your level" className="grid gap-3">
        {LEVELS.map((option) => (
          <button
            key={option.id}
            type="button"
            role="radio"
            aria-checked={level === option.id}
            onClick={() => setLevel(option.id)}
            className="choice px-5 py-4 text-left"
          >
            <span className="block text-[16px] font-bold">{option.title}</span>
            <span className="mt-1 block text-[14px] text-slate-400">{option.body}</span>
          </button>
        ))}
      </div>
    </>
  )
}

function FreeTextStep({ options, value, setValue, placeholder, id }) {
  return (
    <>
      <div className="flex flex-wrap gap-2.5">
        {options.map((option) => (
          <ChipToggle key={option} label={option} selected={value === option} onToggle={() => setValue(value === option ? '' : option)} />
        ))}
      </div>
      <label htmlFor={id} className="mt-5 block text-[13px] font-semibold text-slate-300">
        Or in your own words
      </label>
      <textarea
        id={id}
        dir="auto"
        rows={3}
        maxLength={1000}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder={placeholder}
        className="mt-2 w-full resize-none rounded-xl border-2 border-abyss-700 bg-abyss-900 px-4 py-3 text-[15px] leading-6 text-white placeholder:text-slate-500 focus:border-ember-400 focus:outline-none"
      />
    </>
  )
}

const STEPS = ['interests', 'level', 'background', 'goals']

const QUESTIONS = {
  interests: { question: 'What do you want to learn?', hint: 'Pick as many as you like. Any subject works, not just coding.' },
  level: { question: 'How much do you already know?', hint: null },
  background: { question: 'Tell me a little about yourself', hint: 'Optional. It helps me pitch lessons at the right depth.' },
  goals: { question: 'What’s your goal?', hint: 'Optional. I’ll use it to rank your suggestions.' },
}

export default function OnboardingFlow({ initialProfile, onSubmit, onSkip, submitting, error }) {
  const [step, setStep] = useState(0)
  const [interests, setInterests] = useState(initialProfile?.interests ?? [])
  const [level, setLevel] = useState(initialProfile?.level ?? null)
  const [background, setBackground] = useState(initialProfile?.background ?? '')
  const [goals, setGoals] = useState(initialProfile?.goals ?? '')

  const current = STEPS[step]
  const canContinue = current === 'interests' ? interests.length > 0 : current === 'level' ? Boolean(level) : true
  const isLast = step === STEPS.length - 1
  const progress = ((step + (canContinue ? 1 : 0.4)) / STEPS.length) * 100

  const next = () => {
    if (!canContinue || submitting) return
    if (isLast) {
      onSubmit({
        interests,
        level,
        background: background.trim(),
        goals: goals.trim(),
        preferred_language: 'ar',
      })
    } else {
      setStep(step + 1)
    }
  }

  return (
    <div className="flex min-h-screen flex-col">
      <div className="mx-auto flex w-full max-w-3xl items-center gap-4 px-4 pt-6 sm:px-6">
        <button
          type="button"
          onClick={() => (step === 0 ? onSkip?.() : setStep(step - 1))}
          disabled={step === 0 && !onSkip}
          aria-label={step === 0 ? 'Close and go to the classroom' : 'Previous question'}
          className="grid h-10 w-10 shrink-0 place-items-center rounded-xl text-slate-400 transition hover:bg-white/[0.06] hover:text-white disabled:invisible"
        >
          <BackIcon />
        </button>
        <div
          className="h-4 flex-1 overflow-hidden rounded-full bg-abyss-800"
          role="progressbar"
          aria-label={`Question ${step + 1} of ${STEPS.length}`}
          aria-valuenow={step + 1}
          aria-valuemin={1}
          aria-valuemax={STEPS.length}
        >
          <div
            className="relative h-full rounded-full bg-emerald-400 transition-[width] duration-500 ease-out"
            style={{ width: `${progress}%` }}
          >
            <span className="absolute inset-x-2 top-1 h-1 rounded-full bg-white/30" />
          </div>
        </div>
      </div>

      <div className="mx-auto w-full max-w-3xl flex-1 px-4 pb-10 pt-8 sm:px-6 sm:pt-12">
        <ProfessorSays stepKey={current}>{QUESTIONS[current].question}</ProfessorSays>
        <div key={current} className="step-in">
          {QUESTIONS[current].hint && <p className="mt-2 text-[14px] text-slate-400">{QUESTIONS[current].hint}</p>}
          <div className="mt-6">
            {current === 'interests' && <InterestsStep interests={interests} setInterests={setInterests} />}
            {current === 'level' && <LevelStep level={level} setLevel={setLevel} />}
            {current === 'background' && (
              <FreeTextStep
                id="background"
                options={BACKGROUNDS}
                value={background}
                setValue={setBackground}
                placeholder="e.g. Second-year engineering student, comfortable with math"
              />
            )}
            {current === 'goals' && (
              <FreeTextStep
                id="goals"
                options={GOALS}
                value={goals}
                setValue={setGoals}
                placeholder="e.g. Build my own mobile app by summer"
              />
            )}
          </div>
        </div>
      </div>

      <footer className="sticky bottom-0 border-t-2 border-abyss-800 bg-abyss-900">
        <div className="mx-auto flex w-full max-w-3xl flex-wrap items-center justify-between gap-3 px-4 py-4 sm:px-6 sm:py-5">
          <p role={error ? 'alert' : undefined} className={`text-[14px] ${error ? 'text-red-300' : 'text-slate-500'}`}>
            {error ?? `Question ${step + 1} of ${STEPS.length}`}
          </p>
          <button type="button" onClick={next} disabled={!canContinue || submitting} className="btn-press min-w-[160px] text-[15px] uppercase">
            {submitting ? 'Finding courses…' : isLast ? 'Show my courses' : 'Continue'}
          </button>
        </div>
      </footer>
    </div>
  )
}
