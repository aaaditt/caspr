import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'
import { initBridge, type Bootstrap, type CasprApi } from './bridge'

const MOCK_BOOT: Bootstrap = {
  user: 'Aadit',
  state: 'idle',
  paused: false,
  hotkey: 'right ctrl',
  hotkey_pretty: 'Right Ctrl',
  model: 'large-v3-turbo',
  device: 'auto',
  engine: 'auto',
  language: '',
  injection: 'type',
  pill_linger_s: 6,
  sound_cues: true,
  input_device: null,
  mics: [{ index: 9, name: 'Microphone Array (Realtek(R) Audio)' }],
  startup: false,
  stats: { today: 27, words: 4318, avg_s: 1.7 },
  recent: [
    { id: 3, ts: Date.now() / 1000 - 130, text: "Let's ship the new onboarding flow by Friday and loop in design.", spans: [] },
    { id: 2, ts: Date.now() / 1000 - 840, text: 'Reschedule the standup to eleven thirty tomorrow.', spans: [] },
    { id: 1, ts: Date.now() / 1000 - 3900, text: 'Add a note to the caspr readme about the settings page.', spans: [] },
  ],
}

const LEVEL_BARS = 28

export interface Caspr {
  boot: Bootstrap
  state: string
  detail: string
  paused: boolean
  levels: number[]
  api: CasprApi | null
  refresh(): void
}

const Ctx = createContext<Caspr | null>(null)

export function CasprProvider({ children }: { children: React.ReactNode }) {
  const [boot, setBoot] = useState<Bootstrap>(MOCK_BOOT)
  const [state, setState] = useState('loading')
  const [detail, setDetail] = useState('')
  const [paused, setPaused] = useState(false)
  const [levels, setLevels] = useState<number[]>([])
  const [api, setApi] = useState<CasprApi | null>(null)
  const apiRef = useRef<CasprApi | null>(null)

  const refresh = useCallback(() => {
    apiRef.current?.get_bootstrap((b) => {
      setBoot(b)
      setState(b.state)
      setPaused(b.paused)
    })
  }, [])

  useEffect(() => {
    let live = true
    void initBridge().then((bridgeApi) => {
      if (!live) return
      apiRef.current = bridgeApi
      setApi(bridgeApi)
      if (!bridgeApi) {
        setState('idle') // browser dev: mock mode
        return
      }
      refresh()
      bridgeApi.state_changed.connect((s, d) => {
        setState(s)
        setDetail(d)
        if (s !== 'recording') setLevels([])
      })
      bridgeApi.input_level.connect((level) => {
        setLevels((prev) => [...prev.slice(-(LEVEL_BARS - 1)), Math.min(1, level * 2.2)])
      })
      bridgeApi.paused_changed.connect((p) => setPaused(p))
      bridgeApi.dictation_done.connect(() => refresh())
      bridgeApi.data_changed.connect(() => refresh())
    })
    return () => {
      live = false
    }
  }, [refresh])

  return (
    <Ctx.Provider value={{ boot, state, detail, paused, levels, api, refresh }}>
      {children}
    </Ctx.Provider>
  )
}

export function useCaspr(): Caspr {
  const ctx = useContext(Ctx)
  if (!ctx) throw new Error('useCaspr outside CasprProvider')
  return ctx
}
