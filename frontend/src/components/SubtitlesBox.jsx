import { useMemo, useState } from 'react'

const SPEAKING_STATUSES = new Set(['explaining', 'talking'])

export default function SubtitlesBox({ narration, status }) {
  const [captionsOn, setCaptionsOn] = useState(true)
  const speaking = SPEAKING_STATUSES.has(status)
  const bars = useMemo(() => Array.from({ length: 14 }, (_, index) => index), [])

  return (
    <div
      className="captions-clear-professor pointer-events-none absolute inset-x-0 bottom-0 z-30 bg-gradient-to-t from-black/65 via-black/25 to-transparent px-3 pb-3 pt-12 sm:px-5 sm:pb-4"
      aria-label="Live subtitles and captions"
    >
      <div className="pointer-events-auto relative mx-auto max-w-4xl overflow-hidden rounded-2xl border border-white/10 bg-black/50 px-4 py-2.5 shadow-[0_18px_50px_-25px_rgba(0,0,0,0.95)] backdrop-blur-md sm:px-5">
        <div className="absolute inset-x-8 top-0 h-px bg-gradient-to-r from-transparent via-white/15 to-transparent" />

        <div className="flex items-center justify-between gap-3">
          <span
            className={`flex items-center gap-1.5 text-[8.5px] font-semibold uppercase tracking-[0.2em] ${
              speaking ? 'text-ember-300' : 'text-slate-400'
            }`}
          >
            <span
              className={`h-1.5 w-1.5 rounded-full ${
                speaking ? 'status-pulse bg-ember-400' : 'bg-slate-500'
              }`}
            />
            {speaking ? 'Live subtitles' : 'Subtitles'}
          </span>

          <div className="flex items-center gap-2.5">
            <div className="hidden h-4 items-end gap-[2px] sm:flex" aria-hidden="true">
              {bars.map((index) => (
                <span
                  key={index}
                  className={`w-[2px] rounded-full ${
                    speaking ? 'wave-bar bg-ember-400/70' : 'bg-white/20'
                  }`}
                  style={
                    speaking
                      ? { animationDelay: `${(index % 7) * 0.09}s` }
                      : { height: `${20 + ((index * 11) % 68)}%` }
                  }
                />
              ))}
            </div>
            <span className="font-mono text-[8px] uppercase tracking-[0.14em] text-slate-500">EN</span>
            <button
              type="button"
              onClick={() => setCaptionsOn((value) => !value)}
              aria-pressed={captionsOn}
              aria-label={captionsOn ? 'Hide captions' : 'Show captions'}
              title={captionsOn ? 'Hide captions' : 'Show captions'}
              className={`rounded-md border px-1.5 py-0.5 font-mono text-[9px] font-bold transition ${
                captionsOn
                  ? 'border-ember-500/35 bg-ember-500/10 text-ember-300'
                  : 'border-white/10 bg-white/[0.03] text-slate-500 hover:text-slate-300'
              }`}
            >
              CC
            </button>
          </div>
        </div>

        <p
          className={`mt-1.5 text-center text-[13px] leading-6 ${
            captionsOn
              ? 'text-shadow-cinema text-slate-50'
              : 'text-[11px] italic tracking-wide text-slate-500'
          }`}
        >
          {captionsOn ? (
            <>
              <span className="text-ember-400/90">“</span>
              {narration}
              <span className="text-ember-400/90">”</span>
            </>
          ) : (
            'Captions are hidden. Turn on CC to follow the professor.'
          )}
        </p>
      </div>
    </div>
  )
}
