function SparkIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true" className="h-4 w-4">
      <path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5 18 18M6 18l2.5-2.5M15.5 8.5 18 6" strokeLinecap="round" />
    </svg>
  )
}

const NAV = [
  { id: 'classroom', label: 'Classroom' },
  { id: 'suggestions', label: 'Find a course' },
]

export default function Header({ view, onNavigate, pendingJob, onOpenJob }) {
  return (
    <header className="sticky top-0 z-50 h-16 border-b border-white/[0.07] bg-abyss-900/95 backdrop-blur">
      <div className="flex h-full items-center gap-3 px-4 sm:gap-6 lg:px-5">
        <button type="button" onClick={() => onNavigate('classroom')} className="flex shrink-0 items-center gap-2.5">
          <span className="grid h-9 w-9 place-items-center rounded-xl bg-ember-500">
            <span className="font-mono text-[12px] font-bold text-white">&lt;/&gt;</span>
          </span>
          <span className="hidden text-[16px] font-extrabold tracking-[0.14em] text-white sm:inline">
            <span className="text-ember-400">&lt;</span>CODEU<span className="text-ember-400">&gt;</span>
          </span>
        </button>

        <nav aria-label="Main" className="flex items-center gap-1">
          {NAV.map((item) => {
            const active = view === item.id || (item.id === 'suggestions' && view === 'onboarding')
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => onNavigate(item.id)}
                aria-current={active ? 'page' : undefined}
                className={`whitespace-nowrap rounded-lg px-3 py-2 text-[14px] font-semibold transition ${
                  active ? 'bg-white/[0.08] text-white' : 'text-slate-400 hover:bg-white/[0.04] hover:text-slate-100'
                }`}
              >
                {item.label}
              </button>
            )
          })}
        </nav>

        {pendingJob && view !== 'generating' && (
          <button
            type="button"
            onClick={onOpenJob}
            className="ml-auto flex min-w-0 items-center gap-2 rounded-full border border-ember-500/30 bg-ember-500/10 px-3 py-1.5 text-[13px] font-semibold text-ember-200 transition hover:bg-ember-500/20"
          >
            <span className="status-pulse shrink-0">
              <SparkIcon />
            </span>
            <span className="hidden truncate sm:inline">Building: {pendingJob.topic}</span>
            <span className="sm:hidden">Building…</span>
          </button>
        )}
      </div>
    </header>
  )
}
