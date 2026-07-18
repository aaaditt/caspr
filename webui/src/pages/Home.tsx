import { Card } from '../components/Card'
import { Waveform } from '../components/Waveform'

// Task 1 renders with mock data; the live bridge replaces this next commit.
const MOCK = {
  name: 'Aadit',
  statusTitle: 'Listening ready',
  statusSub: 'large-v3-turbo on CUDA · hold Right Ctrl anywhere and speak',
  stats: [
    { value: '27', caption: 'dictations today' },
    { value: '4,318', caption: 'words dictated' },
    { value: '1.7s', caption: 'avg latency' },
  ],
  recent: [
    { time: '2 min ago', text: "Let's ship the new onboarding flow by Friday and loop in design." },
    { time: '14 min ago', text: 'Reschedule the standup to eleven thirty tomorrow.' },
    { time: '1 h ago', text: 'Add a note to the caspr readme about the new settings page.' },
  ],
}

function greeting(): string {
  const h = new Date().getHours()
  return h < 12 ? 'Good morning' : h < 18 ? 'Good afternoon' : 'Good evening'
}

export function Home() {
  return (
    <div className="flex flex-col gap-5">
      <h1 className="font-display text-[30px] italic leading-tight">
        {greeting()}, {MOCK.name}
      </h1>

      <Card className="flex items-center gap-4 p-5">
        <span className="relative grid h-3 w-3 shrink-0 place-items-center">
          <span className="absolute inset-[-5px] rounded-full bg-amber opacity-40 [animation:pulse-ring_2.6s_ease-out_infinite]" />
          <span className="h-[9px] w-[9px] rounded-full bg-amber shadow-[0_0_12px_rgba(255,183,77,.8)]" />
        </span>
        <div className="min-w-0">
          <div className="text-[13.5px] font-medium">{MOCK.statusTitle}</div>
          <div className="mt-0.5 truncate text-xs text-muted">{MOCK.statusSub}</div>
        </div>
        <div className="ml-auto">
          <Waveform />
        </div>
      </Card>

      <div className="grid grid-cols-3 gap-3">
        {MOCK.stats.map((s) => (
          <Card key={s.caption} className="p-4">
            <div className="text-[26px] font-semibold tabular-nums leading-none text-[#ffd7b8]">
              {s.value}
            </div>
            <div className="mt-1.5 text-[11.5px] text-muted">{s.caption}</div>
          </Card>
        ))}
      </div>

      <div>
        <div className="mb-2 text-[10.5px] font-semibold tracking-[.12em] text-faint">RECENT</div>
        <div className="flex flex-col gap-2">
          {MOCK.recent.map((r, i) => (
            <div key={i} className="flex items-baseline gap-2.5 text-[13.5px]">
              <span className="shrink-0 text-[11.5px] tabular-nums text-faint">{r.time}</span>
              <span className="truncate text-ink">{r.text}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
