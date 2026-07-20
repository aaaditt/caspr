import { bridge } from '../bridge'

export type Page = 'home' | 'history' | 'dictionary' | 'settings'

const NAV: { id: Page; label: string; icon: React.ReactNode }[] = [
  {
    id: 'home',
    label: 'Home',
    icon: <path d="M2.5 8.5 8 3.5l5.5 5V14h-3.8v-3.6H6.3V14H2.5z" />,
  },
  {
    id: 'history',
    label: 'History',
    icon: (
      <>
        <circle cx="8" cy="8" r="5.8" />
        <path d="M8 4.8V8l2.2 2.2" />
      </>
    ),
  },
  {
    id: 'dictionary',
    label: 'Dictionary',
    icon: <path d="M3.2 13.2a1.8 1.8 0 0 1 1.8-1.8h7.8V1.8H5A1.8 1.8 0 0 0 3.2 3.6zm0 0A1.8 1.8 0 0 0 5 15h7.8v-3.6" />,
  },
  {
    id: 'settings',
    label: 'Settings',
    icon: (
      <>
        <path d="M2 5h12M2 11h12" />
        <circle cx="6" cy="5" r="1.7" fill="var(--color-espresso)" />
        <circle cx="10.5" cy="11" r="1.7" fill="var(--color-espresso)" />
      </>
    ),
  },
]

export function Sidebar({ page, onNavigate }: { page: Page; onNavigate: (p: Page) => void }) {
  return (
    <aside className="flex w-47 shrink-0 flex-col border-r border-hairline bg-[#181312]">
      <div
        className="flex items-baseline gap-1.5 px-5 pt-5 pb-6"
        style={{ WebkitAppRegion: 'drag' } as React.CSSProperties}
        onMouseDown={(e) => {
          if (e.button === 0) bridge()?.win_drag()
        }}
      >
        <span className="font-display text-[21px] italic leading-none">caspr</span>
        <span className="h-[5px] w-[5px] rounded-full bg-coral" />
      </div>
      <nav className="flex flex-col gap-0.5 px-2.5">
        {NAV.map((item) => {
          const active = item.id === page
          return (
            <button
              key={item.id}
              onClick={() => onNavigate(item.id)}
              className={`flex items-center gap-2.5 rounded-[10px] px-3 py-2 text-left text-[13.5px] transition-colors ${
                active ? 'bg-raised font-medium text-cream' : 'text-muted hover:text-ink'
              }`}
            >
              <svg
                width="15"
                height="15"
                viewBox="0 0 16 16"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinejoin="round"
                strokeLinecap="round"
                className={active ? 'text-amber' : ''}
              >
                {item.icon}
              </svg>
              {item.label}
            </button>
          )
        })}
      </nav>
    </aside>
  )
}
