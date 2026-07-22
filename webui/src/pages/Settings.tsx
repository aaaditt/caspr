import { useState } from 'react'
import { Card } from '../components/Card'
import { useCaspr } from '../state'

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="mb-2 text-[10.5px] font-semibold tracking-[.12em] text-faint">{title}</div>
      <Card className="flex flex-col gap-1 px-5 py-2">{children}</Card>
    </div>
  )
}

function Row({ label, note, children }: { label: string; note?: string; children: React.ReactNode }) {
  return (
    <div className="flex min-h-12 items-center gap-4 border-b border-hairline py-2 last:border-b-0">
      <span className="w-40 shrink-0 text-[13.5px] text-ink">{label}</span>
      <div className="flex min-w-0 flex-1 items-center justify-end gap-3">
        {note && <span className="text-[11px] text-faint">{note}</span>}
        {children}
      </div>
    </div>
  )
}

function Select({
  value,
  options,
  onChange,
}: {
  value: string
  options: { value: string; label: string }[]
  onChange: (v: string) => void
}) {
  return (
    <div className="relative">
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="appearance-none rounded-[10px] border border-hairline bg-raised py-1.5 pl-3 pr-8 text-[13px] text-cream focus:border-[#3a3028] focus:outline-none"
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
      <svg
        className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-muted"
        width="10"
        height="10"
        viewBox="0 0 10 10"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.4"
      >
        <path d="M2 3.5 5 6.5 8 3.5" />
      </svg>
    </div>
  )
}

function Toggle({ checked, onChange }: { checked: boolean; onChange: (on: boolean) => void }) {
  return (
    <button
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
      className={`relative h-[22px] w-[38px] rounded-full transition-colors ${
        checked ? 'bg-gradient-to-r from-coral to-amber' : 'bg-raised border border-hairline'
      }`}
    >
      <span
        className={`absolute top-[3px] h-4 w-4 rounded-full bg-cream transition-all ${
          checked ? 'left-[18px]' : 'left-[3px]'
        }`}
      />
    </button>
  )
}

const ENGINES = [
  { value: 'auto', label: 'Auto — Parakeet for English' },
  { value: 'parakeet', label: 'Parakeet — English, fastest' },
  { value: 'whisper', label: 'Whisper — all languages' },
]
const MODELS = [
  { value: 'base', label: 'base — fastest' },
  { value: 'small', label: 'small — balanced' },
  { value: 'large-v3-turbo', label: 'large-v3-turbo — best' },
]
const DEVICES = [
  { value: 'auto', label: 'Auto' },
  { value: 'cuda', label: 'GPU (CUDA)' },
  { value: 'cpu', label: 'CPU' },
]
const LANGUAGES = [
  { value: '', label: 'Auto-detect' },
  { value: 'en', label: 'English' },
  { value: 'hi', label: 'हिन्दी' },
]
const INJECTIONS = [
  { value: 'type', label: 'Type (SendInput)' },
  { value: 'clipboard', label: 'Clipboard paste' },
]
const PRESETS = [
  { value: 'ctrl+windows', label: 'Ctrl + Win' },
  { value: 'right ctrl', label: 'Right Ctrl' },
  { value: 'ctrl+alt', label: 'Ctrl + Alt' },
]
const GROQ_MODELS = [
  { value: 'llama-3.1-8b-instant', label: 'Llama 3.1 8B — fastest' },
  { value: 'llama-3.3-70b-versatile', label: 'Llama 3.3 70B — best' },
  { value: 'openai/gpt-oss-20b', label: 'GPT-OSS 20B — balanced' },
]
const TONES = [
  { value: 'balanced', label: 'Balanced' },
  { value: 'casual', label: 'Casual' },
  { value: 'formal', label: 'Formal' },
  { value: 'concise', label: 'Concise' },
  { value: 'verbatim', label: 'Verbatim — minimal edits' },
]

const inputCls =
  'rounded-[10px] border border-hairline bg-raised px-3 py-1.5 text-[13px] text-cream focus:border-[#3a3028] focus:outline-none'

function GroqKey({ isSet, onSave }: { isSet: boolean; onSave: (key: string) => void }) {
  const [draft, setDraft] = useState('')
  return (
    <>
      <input
        type="password"
        value={draft}
        placeholder={isSet ? '•••••••• saved' : 'gsk_…'}
        onChange={(e) => setDraft(e.target.value)}
        className={`w-44 ${inputCls}`}
      />
      <button
        onClick={() => {
          if (draft.trim()) {
            onSave(draft.trim())
            setDraft('')
          }
        }}
        disabled={!draft.trim()}
        className="rounded-[10px] border border-hairline px-3 py-1.5 text-[13px] text-ink transition-colors hover:bg-raised disabled:opacity-50"
      >
        Save
      </button>
    </>
  )
}

function ToneProfiles({
  profiles,
  onChange,
}: {
  profiles: Record<string, string>
  onChange: (next: Record<string, string>) => void
}) {
  const [exe, setExe] = useState('')
  const rows = Object.entries(profiles)
  const remove = (key: string) => {
    const next = { ...profiles }
    delete next[key]
    onChange(next)
  }
  const add = () => {
    const name = exe.trim().toLowerCase()
    if (name) {
      onChange({ ...profiles, [name]: 'casual' })
      setExe('')
    }
  }
  return (
    <div className="flex flex-col gap-2 py-1">
      {rows.length === 0 && (
        <span className="text-[11.5px] text-faint">
          No app-specific tones yet — every app uses the default tone.
        </span>
      )}
      {rows.map(([app, tone]) => (
        <div key={app} className="flex items-center gap-3">
          <span className="w-40 shrink-0 truncate text-[13px] text-ink">{app}</span>
          <div className="flex flex-1 items-center justify-end gap-2">
            <Select value={tone} options={TONES} onChange={(v) => onChange({ ...profiles, [app]: v })} />
            <button
              onClick={() => remove(app)}
              className="rounded-[10px] border border-hairline px-2.5 py-1.5 text-[12px] text-muted transition-colors hover:bg-raised hover:text-coral"
            >
              Remove
            </button>
          </div>
        </div>
      ))}
      <div className="flex items-center gap-3 pt-1">
        <input
          value={exe}
          placeholder="app exe, e.g. slack.exe"
          onChange={(e) => setExe(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && add()}
          className={`w-40 shrink-0 ${inputCls}`}
        />
        <div className="flex flex-1 justify-end">
          <button
            onClick={add}
            disabled={!exe.trim()}
            className="rounded-[10px] border border-hairline px-3 py-1.5 text-[13px] text-ink transition-colors hover:bg-raised disabled:opacity-50"
          >
            Add app
          </button>
        </div>
      </div>
    </div>
  )
}

export function Settings() {
  const { boot, api, refresh } = useCaspr()
  const [capturing, setCapturing] = useState(false)

  const set = (key: string, value: unknown) => {
    api?.set_setting(key, value)
    // small delay lets the Python side persist before we re-pull
    window.setTimeout(refresh, 80)
  }

  const capture = () => {
    if (!api || capturing) return
    setCapturing(true)
    api.capture_hotkey(() => {
      setCapturing(false)
      refresh()
    })
  }

  return (
    <div className="flex flex-col gap-5 pb-4">
      <Section title="DICTATION">
        <Row label="Push-to-talk">
          <span className="rounded-lg border border-hairline bg-raised px-3 py-1.5 text-[12.5px] font-medium tracking-wide text-amber">
            {boot.hotkey_pretty}
          </span>
          <button
            onClick={capture}
            disabled={capturing}
            className="rounded-[10px] border border-hairline px-3 py-1.5 text-[13px] text-ink transition-colors hover:bg-raised disabled:opacity-50"
          >
            {capturing ? 'Press keys…' : 'Change…'}
          </button>
          <Select
            value={PRESETS.some((p) => p.value === boot.hotkey) ? boot.hotkey : ''}
            options={PRESETS.some((p) => p.value === boot.hotkey) ? PRESETS : [{ value: '', label: 'Custom' }, ...PRESETS]}
            onChange={(v) => v && set('hotkey', v)}
          />
        </Row>
        <Row label="Microphone">
          <Select
            value={boot.input_device === null ? '' : String(boot.input_device)}
            options={[
              { value: '', label: 'System default' },
              ...boot.mics.map((m) => ({ value: String(m.index), label: m.name })),
            ]}
            onChange={(v) => set('input_device', v === '' ? null : Number(v))}
          />
        </Row>
        <Row label="Language">
          <Select value={boot.language} options={LANGUAGES} onChange={(v) => set('language', v)} />
        </Row>
        <Row label="Hands-free" note="double-tap to start, tap to stop">
          <Toggle
            checked={boot.handsfree_double_tap}
            onChange={(on) => set('handsfree_double_tap', on)}
          />
        </Row>
        {boot.handsfree_double_tap && (
          <Row label="Double-tap window">
            <input
              type="number"
              min={100}
              max={2000}
              step={50}
              value={boot.double_tap_ms}
              onChange={(e) => set('double_tap_ms', Number(e.target.value))}
              className={`w-20 text-right ${inputCls}`}
            />
            <span className="text-[12.5px] text-muted">ms</span>
          </Row>
        )}
      </Section>

      <Section title="AI CLEANUP">
        <Row label="AI cleanup" note="fixes fillers, punctuation & self-corrections">
          <Toggle checked={boot.cleanup_enabled} onChange={(on) => set('cleanup_enabled', on)} />
        </Row>
        <Row label="Groq API key" note={boot.groq_api_key_set ? 'saved' : 'from console.groq.com'}>
          <GroqKey isSet={boot.groq_api_key_set} onSave={(k) => set('groq_api_key', k)} />
        </Row>
        <Row label="Cleanup model">
          <Select value={boot.groq_model} options={GROQ_MODELS} onChange={(v) => set('groq_model', v)} />
        </Row>
        <Row label="Context window" note="recent dictations sent for consistency">
          <input
            type="number"
            min={0}
            max={50}
            step={1}
            value={boot.cleanup_context_count}
            onChange={(e) => set('cleanup_context_count', Number(e.target.value))}
            className={`w-20 text-right ${inputCls}`}
          />
          <span className="text-[12.5px] text-muted">last</span>
        </Row>
      </Section>

      <Section title="TONE">
        <Row label="Default tone">
          <Select value={boot.tone_default} options={TONES} onChange={(v) => set('tone_default', v)} />
        </Row>
        <div className="border-b border-hairline py-1 last:border-b-0">
          <span className="text-[13.5px] text-ink">Per-app tone</span>
          <ToneProfiles
            profiles={boot.tone_profiles}
            onChange={(next) => set('tone_profiles', next)}
          />
        </div>
      </Section>

      <Section title="TRANSCRIPTION">
        <Row label="Engine" note="applies immediately">
          <Select value={boot.engine} options={ENGINES} onChange={(v) => set('engine', v)} />
        </Row>
        <Row label="Whisper model" note="Whisper engine only">
          <Select value={boot.model} options={MODELS} onChange={(v) => set('model', v)} />
        </Row>
        <Row label="Compute device" note="applies immediately">
          <Select value={boot.device} options={DEVICES} onChange={(v) => set('device', v)} />
        </Row>
      </Section>

      <Section title="OUTPUT">
        <Row label="Text injection">
          <Select value={boot.injection} options={INJECTIONS} onChange={(v) => set('injection', v)} />
        </Row>
      </Section>

      <Section title="FEEDBACK">
        <Row label="Pill linger" note="0 hides the transcript pill">
          <input
            type="number"
            min={0}
            max={30}
            step={0.5}
            value={boot.pill_linger_s}
            onChange={(e) => set('pill_linger_s', Number(e.target.value))}
            className="w-20 rounded-[10px] border border-hairline bg-raised px-3 py-1.5 text-right text-[13px] text-cream focus:border-[#3a3028] focus:outline-none"
          />
          <span className="text-[12.5px] text-muted">s</span>
        </Row>
        <Row label="Sound cues">
          <Toggle checked={boot.sound_cues} onChange={(on) => set('sound_cues', on)} />
        </Row>
      </Section>

      <Section title="SYSTEM">
        <Row label="Launch at login">
          <Toggle
            checked={boot.startup}
            onChange={(on) => {
              api?.set_startup(on)
              window.setTimeout(refresh, 80)
            }}
          />
        </Row>
      </Section>
    </div>
  )
}
