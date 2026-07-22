import { AnimatePresence, motion, useReducedMotion } from 'motion/react'
import { useEffect, useState } from 'react'
import { ResizeEdges } from './components/ResizeEdges'
import { Sidebar, type Page } from './components/Sidebar'
import { TitleBar } from './components/TitleBar'
import { Dictionary } from './pages/Dictionary'
import { History } from './pages/History'
import { Home } from './pages/Home'
import { Settings } from './pages/Settings'
import { CasprProvider } from './state'

const PAGES: Record<Page, React.ComponentType> = {
  home: Home,
  history: History,
  dictionary: Dictionary,
  settings: Settings,
}

export default function App() {
  const [page, setPage] = useState<Page>('home')
  const reduce = useReducedMotion()

  // The host (Qt or Electron) can navigate the app, e.g. an "open history" hotkey.
  useEffect(() => {
    const onNavigate = (e: Event) => {
      const detail = (e as CustomEvent).detail as Page
      if (detail) setPage(detail)
    }
    window.addEventListener('caspr-navigate', onNavigate)
    return () => window.removeEventListener('caspr-navigate', onNavigate)
  }, [])

  const Current = PAGES[page]
  return (
    <CasprProvider>
      <div className="relative flex h-full">
        <ResizeEdges />
        <Sidebar page={page} onNavigate={setPage} />
        <div className="flex min-w-0 flex-1 flex-col">
          <TitleBar />
          <main className="flex-1 overflow-y-auto px-8 pb-8">
            <AnimatePresence mode="wait" initial={false}>
              <motion.div
                key={page}
                initial={reduce ? false : { opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={reduce ? undefined : { opacity: 0, y: -6 }}
                transition={{ duration: 0.18, ease: 'easeOut' }}
                className="h-full"
              >
                <Current />
              </motion.div>
            </AnimatePresence>
          </main>
        </div>
      </div>
    </CasprProvider>
  )
}
