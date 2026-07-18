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
      </Section>

      <Section title="TRANSCRIPTION">
        <Row label="Whisper model" note="applies immediately">
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
