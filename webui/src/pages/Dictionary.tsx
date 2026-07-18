import { useEffect, useState } from 'react'
import { type Dictionary as Dict } from '../bridge'
import { useCaspr } from '../state'

function RemoveButton({ title, onClick }: { title: string; onClick: () => void }) {
  return (
    <button
      title={title}
      onClick={onClick}
      className="grid h-6 w-6 shrink-0 place-items-center rounded-md text-faint opacity-0 transition-all group-hover:opacity-100 hover:bg-raised hover:text-ember"
    >
      <svg width="11" height="11" viewBox="0 0 11 11" fill="none" stroke="currentColor" strokeWidth="1.4">
        <path d="M1.5 1.5l8 8m0-8l-8 8" />
      </svg>
    </button>
  )
}

const EYEBROW = 'mb-2 text-[10.5px] font-semibold tracking-[.12em] text-faint'

export function Dictionary() {
  const { api } = useCaspr()
  const [dict, setDict] = useState<Dict>({ terms: [], rules: [] })
  const [newTerm, setNewTerm] = useState('')

  useEffect(() => {
    if (!api) return
    const fetchDict = () => api.get_dictionary(setDict)
    fetchDict()
    api.data_changed.connect(fetchDict)
    return () => api.data_changed.disconnect(fetchDict)
  }, [api])

  const addTerm = () => {
    const term = newTerm.trim()
    if (term) {
      api?.learn_term(term)
      setNewTerm('')
    }
  }

  return (
    <div className="grid h-full grid-cols-2 gap-6">
      <div className="flex min-h-0 flex-col">
        <div className={EYEBROW}>WORDS CASPR KNOWS</div>
        <input
          value={newTerm}
          onChange={(e) => setNewTerm(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && addTerm()}
          placeholder="Add a word caspr should know…"
          className="mb-3 rounded-xl border border-hairline bg-surface px-4 py-2.5 text-[13.5px] text-cream placeholder:text-faint focus:border-[#3a3028] focus:outline-none"
        />
        {dict.terms.length === 0 ? (
          <p className="mt-4 text-center font-display text-[15px] italic text-muted">
            Words you teach caspr appear here.
          </p>
        ) : (
          <div className="-mx-1 flex-1 overflow-y-auto">
            {dict.terms.map((term) => (
              <div
                key={term}
                className="group flex items-center justify-between rounded-lg px-3 py-1.5 text-[13.5px] text-ink transition-colors hover:bg-surface"
              >
                {term}
                <RemoveButton title={`Forget "${term}"`} onClick={() => api?.forget_term(term)} />
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="flex min-h-0 flex-col">
        <div className={EYEBROW}>REPLACEMENT RULES</div>
        {dict.rules.length === 0 ? (
          <p className="mt-4 text-center font-display text-[15px] italic text-muted">
            Right-click a flagged word in a correction to add a rule.
          </p>
        ) : (
          <div className="-mx-1 flex-1 overflow-y-auto">
            {dict.rules.map((rule) => (
              <div
                key={rule.wrong}
                className="group flex items-center justify-between rounded-lg px-3 py-1.5 text-[13.5px] transition-colors hover:bg-surface"
              >
                <span className="min-w-0 truncate">
                  <span className="text-muted line-through decoration-muted/50">{rule.wrong}</span>
                  <span className="mx-2 text-faint">→</span>
                  <span className="text-ink">{rule.right}</span>
                </span>
                <RemoveButton
                  title={`Remove rule for "${rule.wrong}"`}
                  onClick={() => api?.forget_rule(rule.wrong)}
                />
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
