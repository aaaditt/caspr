import { useEffect, useMemo, useRef, useState } from 'react'
import { type Entry } from '../bridge'
import { FlaggedText } from '../components/FlaggedText'
import { relTime } from '../lib/reltime'
import { useCaspr } from '../state'

function IconButton({
  title,
  onClick,
  danger = false,
  children,
}: {
  title: string
  onClick: () => void
  danger?: boolean
  children: React.ReactNode
}) {
  return (
    <button
      title={title}
      onClick={onClick}
      className={`grid h-7 w-7 place-items-center rounded-lg text-muted transition-colors hover:bg-raised ${
        danger ? 'hover:text-ember' : 'hover:text-cream'
      }`}
    >
      {children}
    </button>
  )
}

export function History() {
  const { boot, api } = useCaspr()
  const [query, setQuery] = useState('')
  const [entries, setEntries] = useState<Entry[] | null>(null)
  const [copiedId, setCopiedId] = useState<number | null>(null)
  const debounce = useRef<number>(undefined)

  const fetchEntries = useMemo(
    () => (q: string) => {
      if (!api) {
        setEntries(boot.recent)
        return
      }
      api.get_history(q, setEntries)
    },
    [api, boot.recent],
  )

  useEffect(() => {
    fetchEntries(query)
    if (!api) return
    const onData = () => fetchEntries(query)
    api.data_changed.connect(onData)
    api.dictation_done.connect(onData)
    return () => {
      api.data_changed.disconnect(onData)
      api.dictation_done.disconnect(onData)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [api])

  const onSearch = (q: string) => {
    setQuery(q)
    window.clearTimeout(debounce.current)
    debounce.current = window.setTimeout(() => fetchEntries(q), 150)
  }

  const copy = (entry: Entry) => {
    api?.copy_text(entry.text)
    setCopiedId(entry.id)
    window.setTimeout(() => setCopiedId(null), 1200)
  }

  return (
    <div className="flex h-full flex-col gap-4">
      <input
        value={query}
        onChange={(e) => onSearch(e.target.value)}
        placeholder="Search dictations…"
        className="w-full rounded-xl border border-hairline bg-surface px-4 py-2.5 text-[13.5px] text-cream placeholder:text-faint focus:border-[#3a3028] focus:outline-none"
      />
      {entries !== null && entries.length === 0 ? (
        <div className="grid flex-1 place-items-center">
          <p className="font-display text-lg italic text-muted">
            {query ? 'No matches.' : `Nothing here yet — hold ${boot.hotkey_pretty} and speak.`}
          </p>
        </div>
      ) : (
        <div className="-mx-2 flex-1 overflow-y-auto pb-2">
          {(entries ?? []).map((entry) => (
            <div
              key={entry.id}
              className="group flex items-start gap-3 rounded-xl px-2 py-2 transition-colors hover:bg-surface"
            >
              <span
                className="mt-0.5 w-[74px] shrink-0 text-right text-[11.5px] tabular-nums text-faint"
                title={new Date(entry.ts * 1000).toLocaleString()}
              >
                {relTime(entry.ts)}
              </span>
              <span className="min-w-0 flex-1 text-[13.5px] leading-relaxed text-ink">
                <FlaggedText text={entry.text} spans={entry.spans} />
              </span>
              <div className="flex shrink-0 gap-0.5 opacity-0 transition-opacity group-hover:opacity-100">
                <IconButton title={copiedId === entry.id ? 'Copied' : 'Copy text'} onClick={() => copy(entry)}>
                  {copiedId === entry.id ? (
                    <svg width="13" height="13" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-amber">
                      <path d="M2 7.5 5.5 11 12 3.5" />
                    </svg>
                  ) : (
                    <svg width="13" height="13" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.3">
                      <rect x="4.5" y="4.5" width="7.5" height="7.5" rx="1.5" />
                      <path d="M9.5 4.5V3A1.5 1.5 0 0 0 8 1.5H3A1.5 1.5 0 0 0 1.5 3v5A1.5 1.5 0 0 0 3 9.5h1.5" />
                    </svg>
                  )}
                </IconButton>
                <IconButton title="Correct — teach caspr" onClick={() => api?.correct(entry.text)}>
                  <svg width="13" height="13" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.3">
                    <path d="M9.8 1.7a1.6 1.6 0 0 1 2.3 2.3L4.8 11.3 1.5 12.5l1.2-3.3z" />
                  </svg>
                </IconButton>
                <IconButton title="Delete" danger onClick={() => api?.delete_entry(entry.id)}>
                  <svg width="13" height="13" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.3">
                    <path d="M1.8 3.5h10.4M5.5 3.5V2.2h3v1.3m-6 0 .6 8.3a1 1 0 0 0 1 .9h3.8a1 1 0 0 0 1-.9l.6-8.3" />
                  </svg>
                </IconButton>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
