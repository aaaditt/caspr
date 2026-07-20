import { bridge } from '../bridge'

/** Transparent drag strip across the top of the main column with the
 *  window controls. Close hides to tray, matching the Qt behavior. */
export function TitleBar() {
  return (
    <div
      className="flex h-11 shrink-0 items-center justify-end pr-2"
      style={{ WebkitAppRegion: 'drag' } as React.CSSProperties}
      onMouseDown={(e) => {
        if (e.button === 0 && e.target === e.currentTarget) bridge()?.win_drag()
      }}
    >
      <button
        title="Minimize"
        style={{ WebkitAppRegion: 'no-drag' } as React.CSSProperties}
        className="grid h-7 w-9 place-items-center rounded-lg text-muted transition-colors hover:bg-raised hover:text-cream"
        onClick={() => bridge()?.win_minimize()}
      >
        <svg width="11" height="11" viewBox="0 0 11 11" fill="none" stroke="currentColor" strokeWidth="1.4">
          <path d="M1 5.5h9" />
        </svg>
      </button>
      <button
        title="Close — caspr keeps running in the tray"
        style={{ WebkitAppRegion: 'no-drag' } as React.CSSProperties}
        className="grid h-7 w-9 place-items-center rounded-lg text-muted transition-colors hover:bg-raised hover:text-ember"
        onClick={() => bridge()?.win_close()}
      >
        <svg width="11" height="11" viewBox="0 0 11 11" fill="none" stroke="currentColor" strokeWidth="1.4">
          <path d="M1.5 1.5l8 8m0-8l-8 8" />
        </svg>
      </button>
    </div>
  )
}
