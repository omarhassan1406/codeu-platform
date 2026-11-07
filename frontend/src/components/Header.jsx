function SearchIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-4 w-4">
      <circle cx="11" cy="11" r="6.5" />
      <path d="m16 16 4 4" strokeLinecap="round" />
    </svg>
  )
}

function FlameIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-4 w-4">
      <path
        d="M12 3c1.6 3.2.4 4.8-1 6.2C9.4 10.9 8 12.4 8 15a4 4 0 0 0 8 0c0-1.6-.6-2.8-1.4-3.8-.4 1-1.1 1.8-2.1 2.3.5-2.7.2-6.2-.5-10.5Z"
        strokeLinejoin="round"
      />
    </svg>
  )
}

const NAV_ITEMS = [
  { label: 'Classroom', href: '#classroom', active: true },
  { label: 'Curriculum', href: '#curriculum' },
  { label: 'Progress', href: '#progress' },
]

export default function Header() {
  return (
    <header className="sticky top-0 z-40 border-b border-white/[0.06] bg-abyss-950/70 backdrop-blur-xl">
      <div className="mx-auto flex h-[72px] max-w-[1640px] items-center gap-3 px-4 sm:gap-4 lg:gap-6 lg:px-8">
        <a href="#classroom" className="flex shrink-0 items-center gap-3">
          <span className="relative grid h-10 w-10 place-items-center overflow-hidden rounded-xl bg-gradient-to-br from-ember-400 via-ember-500 to-ember-600 shadow-[0_10px_30px_-10px_rgba(255,87,34,0.8)]">
            <span className="absolute inset-x-0 top-0 h-px bg-white/40" />
            <span className="font-mono text-[13px] font-bold tracking-tight text-white">&lt;/&gt;</span>
          </span>
          <span className="leading-none">
            <span className="block text-[17px] font-extrabold tracking-[0.16em] text-white">
              <span className="text-ember-400">&lt;</span>CODEU<span className="text-ember-400">&gt;</span>
            </span>
            <span className="mt-1 block text-[9px] font-semibold uppercase tracking-[0.34em] text-slate-500">
              AI Coding Academy
            </span>
          </span>
        </a>

        <nav className="hidden items-center gap-1 lg:flex">
          {NAV_ITEMS.map((item) => (
            <a
              key={item.label}
              href={item.href}
              className={
                item.active
                  ? 'rounded-lg bg-white/[0.06] px-3.5 py-2 text-sm font-semibold text-white ring-1 ring-white/[0.08]'
                  : 'rounded-lg px-3.5 py-2 text-sm font-medium text-slate-400 transition hover:bg-white/[0.04] hover:text-slate-200'
              }
            >
              {item.label}
            </a>
          ))}
        </nav>

        <div className="ml-auto flex items-center gap-2.5">
          <button
            type="button"
            aria-label="Search courses"
            className="grid h-9 w-9 place-items-center rounded-full border border-white/[0.07] bg-white/[0.03] text-slate-400 transition hover:border-ember-500/30 hover:text-ember-300"
          >
            <SearchIcon />
          </button>

          <div className="hidden items-center gap-2 rounded-full border border-white/[0.07] bg-white/[0.03] px-3 py-1.5 sm:flex">
            <FlameIcon />
            <span className="text-xs font-semibold text-slate-200">7-day streak</span>
          </div>

          <button
            type="button"
            className="hidden whitespace-nowrap rounded-full bg-gradient-to-r from-ember-500 to-ember-400 px-4 py-2 text-xs font-bold text-white shadow-lg shadow-ember-500/25 transition hover:brightness-110 min-[420px]:inline-flex"
          >
            Go Pro
          </button>

          <div className="grid h-9 w-9 place-items-center rounded-full bg-abyss-800 text-xs font-bold text-ember-300 ring-1 ring-white/10">
            AK
          </div>
        </div>
      </div>
    </header>
  )
}
