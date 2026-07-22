/**
 * Bridge abstraction: connects to the Python backend via either
 * Electron preload (window.caspr) or QWebChannel (legacy Qt mode).
 *
 * The React code calls bridge() and gets the same CasprApi interface
 * regardless of the runtime environment.
 */

/** Payload shapes mirror caspr/ui/bridge_data.py. */
export interface Entry {
  id: number
  ts: number
  text: string
  spans: [number, number][]
}

export interface Bootstrap {
  user: string
  state: string
  paused: boolean
  hotkey: string
  hotkey_pretty: string
  hotkey_toggle_dictation: string
  hotkey_toggle_dictation_pretty: string
  hotkey_cancel_dictation: string
  hotkey_cancel_dictation_pretty: string
  hotkey_mute_mic: string
  hotkey_mute_mic_pretty: string
  hotkey_open_history: string
  hotkey_open_history_pretty: string
  model: string
  device: string
  engine: string
  language: string
  injection: string
  pill_linger_s: number
  sound_cues: boolean
  cleanup_enabled: boolean
  groq_api_key_set: boolean
  groq_model: string
  cleanup_context_count: number
  tone_default: string
  tone_profiles: Record<string, string>
  handsfree_double_tap: boolean
  double_tap_ms: number
  input_device: number | null
  mics: { index: number; name: string }[]
  startup: boolean
  stats: { today: number; words: number; avg_s: number }
  recent: Entry[]
}

interface QSignal<T extends (...args: never[]) => void> {
  connect(cb: T): void
  disconnect(cb: T): void
}

export interface Dictionary {
  terms: string[]
  rules: { wrong: string; right: string }[]
}

export interface CasprApi {
  win_minimize(): void
  win_close(): void
  win_drag(): void
  win_resize(edge: string): void
  get_bootstrap(cb: (boot: Bootstrap) => void): void
  get_history(query: string, cb: (entries: Entry[]) => void): void
  delete_entry(id: number): void
  copy_text(text: string): void
  correct(text: string): void
  get_dictionary(cb: (d: Dictionary) => void): void
  learn_term(term: string): void
  forget_term(term: string): void
  forget_rule(wrong: string): void
  set_setting(key: string, value: unknown): void
  capture_hotkey(cb: (chord: string | null) => void): void
  set_startup(enabled: boolean): void
  toggle_pause(): void
  state_changed: QSignal<(state: string, detail: string) => void>
  input_level: QSignal<(level: number) => void>
  dictation_done: QSignal<(text: string, spans: [number, number][]) => void>
  paused_changed: QSignal<(paused: boolean) => void>
  data_changed: QSignal<() => void>
}

let api: CasprApi | null = null

export function initBridge(): Promise<CasprApi | null> {
  return new Promise((resolve) => {
    // 1. Try Electron preload bridge (window.caspr injected by preload.js)
    const electronApi = (window as unknown as { caspr?: CasprApi }).caspr
    if (electronApi) {
      api = electronApi
      resolve(api)
      return
    }

    // 2. Try QWebChannel (legacy Qt mode)
    const qt = (window as unknown as { qt?: { webChannelTransport?: object } }).qt
    if (qt?.webChannelTransport) {
      import('qwebchannel').then(({ QWebChannel }) => {
        new QWebChannel(qt.webChannelTransport, (channel) => {
          api = channel.objects.caspr as unknown as CasprApi
          resolve(api)
        })
      }).catch(() => resolve(null))
      return
    }

    // 3. Neither available — mock mode (browser dev)
    resolve(null)
  })
}

export function bridge(): CasprApi | null {
  return api
}
