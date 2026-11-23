import { lazy, Suspense, useEffect, useRef, useState } from 'react'
import { useRecorder } from '../lib/useRecorder'
import RiveAvatar from './RiveAvatar'

// Answers are Markdown (bold, lists, code); reuse the lesson renderer.
const LessonContent = lazy(() => import('./LessonContent'))

const STATUS_LABEL = {
  idle: 'Ready for questions',
  listening: 'Listening…',
  thinking: 'Checking the lesson…',
  talking: 'Speaking',
  explaining: 'Explaining',
}

function HandIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" aria-hidden="true" className="h-4 w-4">
      <path
        d="M8 11V5.5a1.5 1.5 0 0 1 3 0V10m0-5.5V4a1.5 1.5 0 0 1 3 0v6m0-4.5a1.5 1.5 0 0 1 3 0V13a7 7 0 0 1-7 7h-.6a6 6 0 0 1-4.6-2.2L2.6 14.9a1.6 1.6 0 0 1 2.4-2.1L8 15.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

function SendIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true" className="h-4 w-4">
      <path d="m5 12 14-7-5 15-2.5-6.5L5 12Z" strokeLinejoin="round" />
    </svg>
  )
}

function MicIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" aria-hidden="true" className="h-[18px] w-[18px]">
      <rect x="9" y="3" width="6" height="11" rx="3" />
      <path d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21M9 21h6" strokeLinecap="round" />
    </svg>
  )
}

function StopIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" className="h-4 w-4">
      <rect x="6.5" y="6.5" width="11" height="11" rx="2" />
    </svg>
  )
}

function SpeakerIcon({ muted }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" aria-hidden="true" className="h-4 w-4">
      <path d="M4 9.5h3.5L12 5.5v13l-4.5-4H4z" strokeLinejoin="round" />
      {muted ? (
        <path d="m16 9.5 5 5m0-5-5 5" strokeLinecap="round" />
      ) : (
        <path d="M15.5 9a4 4 0 0 1 0 6M18 6.5a7.5 7.5 0 0 1 0 11" strokeLinecap="round" />
      )}
    </svg>
  )
}

const formatClock = (seconds) => `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`

const METER_BARS = 14

// Live input level so learners can see the mic is actually hearing them.
function MicMeter({ level, seconds, max }) {
  const lit = Math.round(level * METER_BARS)
  return (
    <div className="mt-3 flex items-center gap-3 rounded-lg bg-red-500/10 px-3 py-2" aria-live="polite">
      <span className="status-pulse h-2 w-2 shrink-0 rounded-full bg-red-400" />
      <span className="text-[13px] font-semibold text-red-100">
        Recording {formatClock(seconds)} / {formatClock(max)}
      </span>
      <span className="ml-auto flex h-4 items-end gap-[3px]" aria-label={lit ? 'Hearing you' : 'No sound yet'}>
        {Array.from({ length: METER_BARS }, (_, i) => (
          <span
            key={i}
            className={`w-[3px] rounded-full ${i < lit ? 'bg-red-300' : 'bg-white/15'}`}
            style={{ height: `${30 + ((i * 37) % 70)}%` }}
          />
        ))}
      </span>
    </div>
  )
}

const ACTIVITY_TEXT = {
  transcribing: 'Turning your voice into text…',
  answering: 'Checking the lesson for an answer…',
  voice: 'Preparing the professor’s voice…',
  lecture: 'Preparing the lesson explanation…',
}

// Freemium allowance: shown only when the server enforces a limit.
function QuotaLine({ quota }) {
  if (!quota || quota.limit == null) return null
  const left = quota.remaining ?? 0
  return (
    <p className={`mt-2 text-[12px] font-semibold ${left === 0 ? 'text-amber-200' : 'text-slate-300'}`} aria-live="polite">
      {left === 0
        ? 'No questions left today. They reset at midnight UTC.'
        : `${left} of ${quota.limit} questions left today`}
    </p>
  )
}

function ActivityLine({ activity, heard }) {
  return (
    <div className="mt-3 space-y-1" aria-live="polite">
      {heard && (
        <p dir="auto" className="text-[12.5px] text-slate-300">
          Heard: <span className="text-white">“{heard}”</span>
        </p>
      )}
      <p className="text-[13px] text-amber-200">{ACTIVITY_TEXT[activity] ?? ACTIVITY_TEXT.answering}</p>
    </div>
  )
}

function CloseIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true" className="h-4 w-4">
      <path d="m6 6 12 12M18 6 6 18" strokeLinecap="round" />
    </svg>
  )
}

function AnswerCard({ exchange, onReplay, speaking }) {
  const [showSources, setShowSources] = useState(false)
  return (
    <div className="mt-3 rounded-xl border border-white/[0.08] bg-abyss-900 p-3.5">
      <p dir="auto" className="text-[12px] text-slate-400">
        You asked: <span className="text-slate-200">{exchange.question}</span>
      </p>
      <div className="answer-prose scrollbar-thin mt-2 max-h-64 overflow-y-auto pr-1">
        <Suspense fallback={<p dir="auto" className="whitespace-pre-wrap text-[14px] leading-7 text-slate-100">{exchange.answer}</p>}>
          <LessonContent markdown={exchange.answer} />
        </Suspense>
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-[12px]">
        {exchange.grounded ? (
          <button
            type="button"
            onClick={() => setShowSources((v) => !v)}
            aria-expanded={showSources}
            className="font-semibold text-emerald-300 underline-offset-4 hover:underline"
          >
            From {exchange.sources.length} lesson excerpt{exchange.sources.length === 1 ? '' : 's'}
          </button>
        ) : (
          <span className="text-amber-300">Not covered in this course</span>
        )}
        {!speaking && (
          <button type="button" onClick={onReplay} className="font-semibold text-slate-300 hover:text-white">
            Replay captions
          </button>
        )}
      </div>
      {showSources && (
        <ol className="scrollbar-thin mt-2 max-h-40 space-y-2 overflow-y-auto">
          {exchange.sources.map((source, i) => (
            <li key={i} dir="auto" className="rounded-lg bg-white/[0.04] px-3 py-2 text-[12px] leading-5 text-slate-400">
              {source.length > 280 ? `${source.slice(0, 280)}…` : source}
            </li>
          ))}
        </ol>
      )}
    </div>
  )
}

export default function Professor({ tutor, disabled }) {
  const [open, setOpen] = useState(false)
  const [question, setQuestion] = useState('')
  const inputRef = useRef(null)
  const recorder = useRecorder()
  const busy = tutor.status === 'thinking'
  const outOfQuestions = tutor.quota?.remaining === 0

  useEffect(() => {
    if (open) inputRef.current?.focus()
  }, [open])

  const openPanel = () => {
    setOpen(true)
    tutor.startListening()
  }

  const closePanel = () => {
    setOpen(false)
    if (recorder.recording) recorder.stop() // discard the recording
    if (tutor.status === 'listening') tutor.stop()
  }

  const toggleRecording = async () => {
    if (recorder.recording) {
      const { blob, reason } = await recorder.stop()
      if (blob) {
        setQuestion('')
        await tutor.askByVoice(blob)
      } else {
        tutor.rejectRecording(reason) // silent or accidental tap: say so, never guess
      }
      return
    }
    tutor.startListening()
    await recorder.start()
  }

  const submit = (event) => {
    event.preventDefault()
    const text = question.trim()
    if (text.length < 2 || busy) return
    tutor.ask(text)
    setQuestion('')
  }

  return (
    <div className="pointer-events-none fixed bottom-0 left-0 z-40 flex items-end">
      {/* Standalone avatar: no bubble; RiveAvatar stays invisible until Rive is ready. */}
      <RiveAvatar
        status={tutor.status}
        className="pointer-events-none h-[160px] w-[124px] shrink-0 lg:h-[230px] lg:w-[180px] xl:h-[290px] xl:w-[228px]"
      />

      <div className="pointer-events-auto mb-4 -ml-2 w-[min(380px,calc(100vw-150px))] lg:mb-6 lg:-ml-6">
        {open && (
          <div
            role="dialog"
            aria-label="Ask the professor"
            className="step-in mb-3 rounded-2xl border border-white/[0.09] bg-abyss-800 p-4 shadow-[0_24px_60px_-20px_rgba(0,0,0,0.7)]"
          >
            <div className="flex items-center justify-between gap-2">
              <p className="text-[14px] font-bold text-white">Ask about this lesson</p>
              <div className="flex items-center gap-1">
                <button
                  type="button"
                  onClick={() => tutor.setVoiceOn(!tutor.voiceOn)}
                  aria-pressed={tutor.voiceOn}
                  aria-label={tutor.voiceOn ? 'Voice on. Turn the professor’s voice off' : 'Voice off. Turn the professor’s voice on'}
                  className={`flex h-7 items-center gap-1.5 rounded-full border px-2.5 text-[12px] font-semibold transition ${
                    tutor.voiceOn
                      ? 'border-emerald-400/40 bg-emerald-400/10 text-emerald-200 hover:bg-emerald-400/20'
                      : 'border-white/15 bg-white/[0.04] text-slate-300 hover:bg-white/[0.08]'
                  }`}
                >
                  <SpeakerIcon muted={!tutor.voiceOn} />
                  {tutor.voiceOn ? 'Voice on' : 'Voice off'}
                </button>
                <button
                  type="button"
                  onClick={closePanel}
                  aria-label="Close question panel"
                  className="grid h-7 w-7 place-items-center rounded-lg text-slate-400 transition hover:bg-white/[0.06] hover:text-white"
                >
                  <CloseIcon />
                </button>
              </div>
            </div>
            <p className="mt-1 text-[12px] leading-5 text-slate-400">
              Answers come only from this course. If it isn&apos;t covered, the professor will say so.
            </p>
            <QuotaLine quota={tutor.quota} />

            <form onSubmit={submit} className="mt-3 flex items-end gap-2">
              <label className="sr-only" htmlFor="tutor-question">
                Your question
              </label>
              <textarea
                id="tutor-question"
                ref={inputRef}
                dir="auto"
                rows={2}
                maxLength={1000}
                value={question}
                disabled={busy || recorder.recording}
                onChange={(event) => setQuestion(event.target.value)}
                onFocus={() => tutor.status === 'idle' && !tutor.speaking && tutor.startListening()}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' && !event.shiftKey) submit(event)
                  if (event.key === 'Escape') closePanel()
                }}
                placeholder={
                  recorder.recording
                    ? `Listening… ${formatClock(recorder.seconds)} / ${formatClock(recorder.maxSeconds)}. Tap the mic to send.`
                    : 'Type, or tap the mic and speak (Arabic or English)'
                }
                className="scrollbar-thin min-h-[44px] flex-1 resize-none rounded-xl border border-white/[0.1] bg-abyss-900 px-3 py-2.5 text-[14px] leading-6 text-white placeholder:text-slate-500 focus:border-ember-400/60 focus:outline-none disabled:opacity-60"
              />
              <button
                type="button"
                onClick={toggleRecording}
                disabled={busy || (outOfQuestions && !recorder.recording)}
                aria-pressed={recorder.recording}
                aria-label={recorder.recording ? 'Stop recording and send' : 'Ask by voice'}
                className={`relative grid h-11 w-11 shrink-0 place-items-center rounded-xl transition disabled:opacity-50 ${
                  recorder.recording
                    ? 'bg-red-500 text-white hover:bg-red-400'
                    : 'border border-white/[0.12] bg-abyss-900 text-slate-200 hover:border-ember-400/60 hover:text-white'
                }`}
              >
                {recorder.recording && <span className="status-pulse absolute inset-0 rounded-xl ring-2 ring-red-400/60" />}
                {recorder.recording ? <StopIcon /> : <MicIcon />}
              </button>
              <button
                type="submit"
                disabled={busy || outOfQuestions || question.trim().length < 2}
                aria-label="Send question"
                className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-ember-500 text-white transition hover:bg-ember-400 disabled:bg-abyss-700 disabled:text-slate-500"
              >
                <SendIcon />
              </button>
            </form>

            {recorder.recording && <MicMeter level={recorder.level} seconds={recorder.seconds} max={recorder.maxSeconds} />}
            {busy && <ActivityLine activity={tutor.activity} heard={tutor.heard} />}
            {tutor.speaking && tutor.voiceOn && !busy && (
              <p className="mt-3 flex items-center gap-2 text-[13px] text-emerald-200" aria-live="polite">
                <SpeakerIcon muted={false} />
                Speaking… press Stop to interrupt.
              </p>
            )}
            {!tutor.voiceOn && tutor.exchange && !busy && (
              <p className="mt-3 text-[12.5px] text-slate-400">Voice is off, so answers show as captions only.</p>
            )}
            {recorder.error && (
              <p role="alert" className="mt-3 rounded-lg bg-amber-500/10 px-3 py-2 text-[13px] text-amber-100">
                {recorder.error}
              </p>
            )}
            {tutor.voiceNotice && !busy && <p className="mt-3 text-[12.5px] text-slate-400">{tutor.voiceNotice}</p>}
            {tutor.error && (
              <p role="alert" className="mt-3 rounded-lg bg-red-500/10 px-3 py-2 text-[13px] text-red-200">
                {tutor.error}
              </p>
            )}
            {tutor.exchange && !busy && (
              <AnswerCard exchange={tutor.exchange} onReplay={tutor.replay} speaking={tutor.speaking} />
            )}
          </div>
        )}

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={open ? closePanel : openPanel}
            disabled={disabled}
            aria-expanded={open}
            className="flex items-center gap-2 rounded-full bg-ember-500 px-4 py-2.5 text-[14px] font-bold text-white shadow-[0_10px_30px_-10px_rgba(255,87,34,0.7)] transition hover:bg-ember-400 disabled:bg-abyss-700 disabled:text-slate-500 disabled:shadow-none"
          >
            <HandIcon />
            {open ? 'Hide question' : 'Raise hand'}
          </button>
          {tutor.speaking && (
            <button
              type="button"
              onClick={tutor.stop}
              className="rounded-full border border-white/15 bg-abyss-800 px-3 py-2 text-[13px] font-semibold text-slate-200 transition hover:text-white"
            >
              Stop
            </button>
          )}
          <span className="hidden rounded-full bg-abyss-800/90 px-3 py-1.5 text-[12px] font-medium text-slate-300 sm:inline" aria-live="polite">
            {recorder.recording ? 'Listening to you…' : (STATUS_LABEL[tutor.status] ?? STATUS_LABEL.idle)}
          </span>
        </div>
      </div>
    </div>
  )
}
