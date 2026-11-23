import { useState } from 'react'
import RiveAvatar from '../RiveAvatar'

function BookIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" aria-hidden="true" className="h-5 w-5">
      <path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v15H6.5A2.5 2.5 0 0 0 4 20.5v-15Z" strokeLinejoin="round" />
      <path d="M4 20.5A2.5 2.5 0 0 1 6.5 18H20v3H6.5A2.5 2.5 0 0 1 4 20.5Z" strokeLinejoin="round" />
    </svg>
  )
}

function SparkIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" aria-hidden="true" className="h-5 w-5">
      <path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5 18 18M6 18l2.5-2.5M15.5 8.5 18 6" strokeLinecap="round" />
    </svg>
  )
}

function SuggestionRow({ suggestion, onOpen, onGenerate, busy }) {
  const existing = suggestion.kind === 'existing'
  return (
    <li className="choice flex flex-col gap-4 p-5 sm:flex-row sm:items-center">
      <span
        className={`grid h-11 w-11 shrink-0 place-items-center rounded-xl ${
          existing ? 'bg-emerald-400/15 text-emerald-300' : 'bg-ember-500/15 text-ember-300'
        }`}
      >
        {existing ? <BookIcon /> : <SparkIcon />}
      </span>
      <div className="min-w-0 flex-1">
        <p dir="auto" className="text-[16px] font-bold leading-6 text-white">
          {suggestion.title}
        </p>
        <p className="mt-1 text-[13.5px] leading-5 text-slate-400">
          <span className={existing ? 'text-emerald-300' : 'text-ember-300'}>
            {existing ? 'Ready now' : 'New course'}
          </span>
          {' · '}
          {suggestion.reason}
        </p>
      </div>
      {existing ? (
        <button type="button" onClick={() => onOpen(suggestion.course_id)} className="btn-press shrink-0 text-[14px]">
          Start learning
        </button>
      ) : (
        <button
          type="button"
          disabled={busy}
          onClick={() => onGenerate(suggestion.generation_topic)}
          className="choice shrink-0 px-5 py-2.5 text-[14px] font-bold disabled:cursor-not-allowed disabled:opacity-50"
        >
          Generate course
        </button>
      )}
    </li>
  )
}

export default function SuggestionsView({ suggestions, onOpen, onGenerate, onEditProfile, generateError, busy }) {
  const [topic, setTopic] = useState('')
  const cleanTopic = topic.replace(/\s+/g, ' ').trim()
  const validTopic = cleanTopic.length >= 3 && cleanTopic.length <= 200

  const submitCustom = (event) => {
    event.preventDefault()
    if (validTopic && !busy) onGenerate(cleanTopic)
  }

  return (
    <div className="step-in mx-auto w-full max-w-3xl px-4 pb-16 pt-8 sm:px-6 sm:pt-12">
      <div className="flex items-end gap-4">
        <RiveAvatar status="explaining" className="h-[130px] w-[104px] shrink-0 sm:h-[160px] sm:w-[128px]" />
        <div className="mb-5">
          <h1 className="text-[24px] font-bold leading-8 text-white sm:text-[28px]">Here’s where I’d start</h1>
          <p className="mt-1 text-[14.5px] text-slate-400">
            Open a finished course now, or have me build a new one around your interests.
          </p>
        </div>
      </div>

      {suggestions.length > 0 ? (
        <ul className="mt-8 space-y-3">
          {suggestions.map((s) => (
            <SuggestionRow
              key={`${s.kind}:${s.course_id ?? s.generation_topic}`}
              suggestion={s}
              onOpen={onOpen}
              onGenerate={onGenerate}
              busy={busy}
            />
          ))}
        </ul>
      ) : (
        <p className="mt-8 rounded-2xl border-2 border-dashed border-abyss-700 p-6 text-center text-[15px] text-slate-400">
          No matches yet. Describe a topic below and I’ll generate a course for it.
        </p>
      )}

      <form onSubmit={submitCustom} className="mt-10 rounded-2xl border-2 border-abyss-700 bg-abyss-850 p-5">
        <label htmlFor="custom-course" className="text-[16px] font-bold text-white">
          Want something else?
        </label>
        <p className="mt-1 text-[13.5px] text-slate-400">Name any topic and level. Generation takes a few minutes.</p>
        <div className="mt-4 flex flex-col gap-3 sm:flex-row">
          <input
            id="custom-course"
            dir="auto"
            value={topic}
            maxLength={200}
            onChange={(e) => setTopic(e.target.value)}
            placeholder="e.g. Linear algebra for machine learning"
            className="min-w-0 flex-1 rounded-xl border-2 border-abyss-700 bg-abyss-900 px-4 py-3 text-[15px] text-white placeholder:text-slate-500 focus:border-ember-400 focus:outline-none"
          />
          <button type="submit" disabled={!validTopic || busy} className="btn-press text-[14px]">
            Generate
          </button>
        </div>
        {generateError && (
          <p role="alert" className="mt-3 text-[13.5px] text-red-300">
            {generateError}
          </p>
        )}
      </form>

      <button
        type="button"
        onClick={onEditProfile}
        className="mt-6 text-[14px] font-semibold text-slate-400 underline-offset-4 transition hover:text-white hover:underline"
      >
        Change my answers
      </button>
    </div>
  )
}
