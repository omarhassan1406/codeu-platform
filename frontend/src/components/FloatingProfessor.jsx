import RiveAvatar from './RiveAvatar'

const QUICK_STATES = [
  { id: 'idle', label: 'Idle', dot: 'bg-slate-400' },
  { id: 'listening', label: 'Listen', dot: 'bg-emerald-400' },
  { id: 'thinking', label: 'Think', dot: 'bg-amber-400' },
  { id: 'talking', label: 'Talk', dot: 'bg-sky-400' },
  { id: 'explaining', label: 'Explain', dot: 'bg-ember-400' },
]

const STATUS_META = {
  idle: {
    label: 'Idle',
    hint: 'Ready when you are',
    dot: 'bg-slate-400',
    chip: 'border-slate-400/20 bg-slate-400/10 text-slate-300',
  },
  listening: {
    label: 'Listening',
    hint: 'Capturing your question',
    dot: 'bg-emerald-400',
    chip: 'border-emerald-400/25 bg-emerald-400/10 text-emerald-300',
  },
  thinking: {
    label: 'Thinking',
    hint: 'Searching lesson context',
    dot: 'bg-amber-400',
    chip: 'border-amber-400/25 bg-amber-400/10 text-amber-300',
  },
  talking: {
    label: 'Talking',
    hint: 'Delivering the answer',
    dot: 'bg-sky-400',
    chip: 'border-sky-400/25 bg-sky-400/10 text-sky-300',
  },
  explaining: {
    label: 'Explaining',
    hint: 'Walking through the code',
    dot: 'bg-ember-400',
    chip: 'border-ember-500/30 bg-ember-500/10 text-ember-300',
  },
}

function MicIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-3.5 w-3.5">
      <rect x="9" y="3" width="6" height="11" rx="3" />
      <path d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21M9 21h6" strokeLinecap="round" />
    </svg>
  )
}

function PauseIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-3.5 w-3.5">
      <rect x="7" y="5" width="3.5" height="14" rx="1.2" />
      <rect x="13.5" y="5" width="3.5" height="14" rx="1.2" />
    </svg>
  )
}

export default function FloatingProfessor({ status, onStatusChange }) {
  const meta = STATUS_META[status] ?? STATUS_META.idle

  return (
    <aside
      aria-label="AI professor"
      className="professor-in professor-float pointer-events-none relative z-30 mt-4 w-full max-w-xl"
    >
      <div className="professor-shell relative overflow-hidden rounded-2xl border border-white/[0.07] bg-abyss-850/85 p-3 backdrop-blur-xl">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-x-6 bottom-24 top-8 rounded-full bg-[radial-gradient(circle_at_50%_55%,rgba(255,87,34,0.2),transparent_65%)] blur-2xl"
        />

        <div className="professor-layout relative flex items-center gap-3">
          <div className="professor-stage pointer-events-auto relative h-[176px] w-[132px] shrink-0 sm:h-[196px] sm:w-[152px]">
            <div
              aria-hidden="true"
              className="absolute inset-x-[18%] bottom-2 h-6 rounded-full bg-black/60 blur-xl"
            />
            <RiveAvatar status={status} className="relative h-full w-full" />
          </div>

          <div className="professor-dock pointer-events-auto relative min-w-0 flex-1 rounded-xl border border-white/[0.08] bg-abyss-900/75 p-1.5 shadow-[0_24px_60px_-30px_rgba(0,0,0,0.95)] backdrop-blur-xl">
            <div className="flex items-center justify-between gap-2 px-1 pb-1.5">
              <span className="flex items-center gap-1.5 text-[7.5px] font-semibold uppercase tracking-[0.16em] text-slate-400">
                <span className="status-pulse h-1.5 w-1.5 rounded-full bg-emerald-400" />
                AI professor
              </span>
              <span
                className={`flex items-center gap-1 rounded-full border px-1.5 py-0.5 text-[7.5px] font-semibold uppercase tracking-[0.12em] ${meta.chip}`}
              >
                <span className={`h-1 w-1 rounded-full ${meta.dot}`} />
                {meta.label}
              </span>
            </div>

            <div className="flex items-center gap-0.5">
              {QUICK_STATES.map((state) => {
                const active = state.id === status
                return (
                  <button
                    key={state.id}
                    type="button"
                    onClick={() => onStatusChange(state.id)}
                    aria-pressed={active}
                    className={`flex flex-1 flex-col items-center gap-1 rounded-lg border py-1.5 transition lg:rounded-xl ${
                      active
                        ? 'border-ember-500/35 bg-ember-500/10 text-ember-200'
                        : 'border-transparent text-slate-500 hover:bg-white/[0.04] hover:text-slate-300'
                    }`}
                  >
                    <span className={`h-1.5 w-1.5 rounded-full ${state.dot}`} />
                    <span className="text-[7.5px] font-semibold uppercase tracking-[0.08em]">
                      {state.label}
                    </span>
                  </button>
                )
              })}
            </div>

            <div className="mt-1 flex items-center gap-1.5">
              <button
                type="button"
                onClick={() => onStatusChange('listening')}
                className="flex flex-1 items-center justify-center gap-1.5 rounded-lg bg-gradient-to-r from-ember-500 to-ember-400 px-3 py-2 text-[10.5px] font-bold text-white shadow-lg shadow-ember-500/25 transition hover:brightness-110"
              >
                <MicIcon />
                Raise hand
              </button>
              <button
                type="button"
                onClick={() => onStatusChange('idle')}
                aria-label="Pause AI professor"
                title={meta.hint}
                className="grid h-8 w-8 shrink-0 place-items-center rounded-lg border border-white/[0.07] bg-white/[0.02] text-slate-400 transition hover:border-white/15 hover:text-slate-200"
              >
                <PauseIcon />
              </button>
            </div>
          </div>
        </div>
      </div>
    </aside>
  )
}
