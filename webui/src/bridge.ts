import { QWebChannel } from 'qwebchannel'

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
  model: string
  device: string
  language: string
  injection: string
  pill_linger_s: number
  sound_cues: boolean
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

/** The Python Bridge object registered as "caspr" on the web channel.
 *  Slot return values arrive via a trailing callback (qwebchannel style).
 *  Outside Qt (plain browser dev), initBridge resolves null → mock mode. */
export interface CasprApi {
  win_minimize(): void
  win_close(): void
  win_drag(): void
  win_resize(edge: string): void
  get_bootstrap(cb: (boot: Bootstrap) => void): void
  state_changed: QSignal<(state: string, detail: string) => void>
  input_level: QSignal<(level: number) => void>
  dictation_done: QSignal<(text: string, spans: [number, number][]) => void>
  paused_changed: QSignal<(paused: boolean) => void>
}

let api: CasprApi | null = null

export function initBridge(): Promise<CasprApi | null> {
  return new Promise((resolve) => {
    const qt = (window as unknown as { qt?: { webChannelTransport?: object } }).qt
    if (!qt?.webChannelTransport) {
      resolve(null)
      return
    }
    new QWebChannel(qt.webChannelTransport, (channel) => {
      api = channel.objects.caspr as unknown as CasprApi
      resolve(api)
    })
  })
}

export function bridge(): CasprApi | null {
  return api
}
