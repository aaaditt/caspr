import { motion, useReducedMotion } from 'motion/react'
import { useEffect, useState } from 'react'
import { Card } from '../components/Card'
import { FlaggedText } from '../components/FlaggedText'
import { Waveform } from '../components/Waveform'
import { relTime } from '../lib/reltime'
import { useCaspr } from '../state'

const stagger = {
  hidden: {},
  show: { transition: { staggerChildren: 0.055 } },
}
const rise = {
  hidden: { opacity: 0, y: 10 },
  show: { opacity: 1, y: 0, transition: { duration: 0.28, ease: 'easeOut' as const } },
}

const DOT: Record<string, string> = {
  loading: 'bg-muted',
  idle: 'bg-amber shadow-[0_0_12px_rgba(255,183,77,.8)]',
  recording: 'bg-ember shadow-[0_0_14px_rgba(255,92,73,.9)]',
  processing: 'bg-coral shadow-[0_0_12px_rgba(255,138,101,.8)]',
  error: 'bg-[#e05252] shadow-[0_0_12px_rgba(224,82,82,.8)]',
  paused: 'bg-[#b8a06a]',
}

function greeting(): string {
  const h = new Date().getHours()
  return h < 12 ? 'Good morning' : h < 18 ? 'Good afternoon' : 'Good evening'
}

export function Home() {
  const { boot, state, detail, paused, levels } = useCaspr()
  const reduce = useReducedMotion()
  const [, tick] = useState(0)
  useEffect(() => {
    const id = setInterval(() => tick((n) => n + 1), 30_000) // keep rel times fresh
    return () => clearInterval(id)
  }, [])

  const effective = paused ? 'paused' : state
  const title = paused
    ? 'Paused'
    : state === 'loading'
      ? 'Warming up'
      : state === 'recording'
        ? 'Listening…'
        : state === 'processing'
          ? 'Transcribing…'
          : state === 'error'
            ? 'Something went wrong'
            : 'Listening ready'
  const sub = paused
    ? 'Push-to-talk is off — resume from the tray'
    : state === 'idle'
      ? `${detail || boot.model} · hold ${boot.hotkey_pretty} anywhere and speak`
      : detail || (state === 'loading' ? `loading ${boot.model}…` : '')

  return (
    <motion.div
      className="flex flex-col gap-5"
      variants={reduce ? undefined : stagger}
      initial="hidden"
      animate="show"
    >
      <motion.h1 variants={rise} className="font-display text-[30px] italic leading-tight">
        {greeting()}, {boot.user}
      </motion.h1>

      <motion.div variants={rise}>
      <Card className="flex items-center gap-4 p-5">
        <span className="relative grid h-3 w-3 shrink-0 place-items-center">
          {(effective === 'idle' || effective === 'recording') && (
            <span
              className={`absolute inset-[-5px] rounded-full opacity-40 [animation:pulse-ring_2.6s_ease-out_infinite] ${
                effective === 'recording' ? 'bg-ember' : 'bg-amber'
              }`}
            />
          )}
          <span className={`h-[9px] w-[9px] rounded-full ${DOT[effective] ?? 'bg-muted'}`} />
        </span>
        <div className="min-w-0">
          <div className="text-[13.5px] font-medium">{title}</div>
          <div className="mt-0.5 truncate text-xs text-muted">{sub}</div>
        </div>
        <div className="ml-auto">
          <Waveform
            levels={state === 'recording' ? levels : undefined}
            animated={!reduce && (state === 'recording' || state === 'processing')}
          />
        </div>
      </Card>
      </motion.div>

      <motion.div variants={rise} className="grid grid-cols-3 gap-3">
        {[
          { value: String(boot.stats.today), caption: 'dictations today' },
          { value: boot.stats.words.toLocaleString('en'), caption: 'words dictated' },
          { value: boot.stats.avg_s ? `${boot.stats.avg_s.toFixed(1)}s` : '—', caption: 'avg latency' },
        ].map((s) => (
          <Card
            key={s.caption}
            className="p-4 transition-transform duration-200 hover:-translate-y-0.5"
          >
            <div className="text-[26px] font-semibold tabular-nums leading-none text-[#ffd7b8]">
              {s.value}
            </div>
            <div className="mt-1.5 text-[11.5px] text-muted">{s.caption}</div>
          </Card>
        ))}
      </motion.div>

      <motion.div variants={rise}>
        <div className="mb-2 text-[10.5px] font-semibold tracking-[.12em] text-faint">RECENT</div>
        {boot.recent.length === 0 ? (
          <p className="font-display text-[15px] italic text-muted">
            Nothing here yet — hold {boot.hotkey_pretty} and speak.
          </p>
        ) : (
          <div className="flex flex-col gap-2">
            {boot.recent.map((r) => (
              <div key={r.id} className="flex items-baseline gap-2.5 text-[13.5px]">
                <span className="shrink-0 text-[11.5px] tabular-nums text-faint">
                  {relTime(r.ts)}
                </span>
                <span className="truncate text-ink">
                  <FlaggedText text={r.text} spans={r.spans} />
                </span>
              </div>
            ))}
          </div>
        )}
      </motion.div>
    </motion.div>
  )
}
