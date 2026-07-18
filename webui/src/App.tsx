import { useState } from 'react'
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

  const Current = PAGES[page]
  return (
    <CasprProvider>
      <div className="relative flex h-full">
        <ResizeEdges />
        <Sidebar page={page} onNavigate={setPage} />
        <div className="flex min-w-0 flex-1 flex-col">
          <TitleBar />
          <main className="flex-1 overflow-y-auto px-8 pb-8">
            <Current />
          </main>
        </div>
      </div>
    </CasprProvider>
  )
}
