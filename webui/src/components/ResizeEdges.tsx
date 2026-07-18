import { bridge } from '../bridge'

const ZONES: { edge: string; className: string }[] = [
  { edge: 'top', className: 'top-0 left-2.5 right-2.5 h-[5px] cursor-ns-resize' },
  { edge: 'bottom', className: 'bottom-0 left-2.5 right-2.5 h-[5px] cursor-ns-resize' },
  { edge: 'left', className: 'left-0 top-2.5 bottom-2.5 w-[5px] cursor-ew-resize' },
  { edge: 'right', className: 'right-0 top-2.5 bottom-2.5 w-[5px] cursor-ew-resize' },
  { edge: 'topleft', className: 'top-0 left-0 h-2.5 w-2.5 cursor-nwse-resize' },
  { edge: 'topright', className: 'top-0 right-0 h-2.5 w-2.5 cursor-nesw-resize' },
  { edge: 'bottomleft', className: 'bottom-0 left-0 h-2.5 w-2.5 cursor-nesw-resize' },
  { edge: 'bottomright', className: 'bottom-0 right-0 h-2.5 w-2.5 cursor-nwse-resize' },
]

/** Invisible strips along the frameless window's edges; mousedown hands the
 *  gesture to Windows via startSystemResize, so snapping keeps working. */
export function ResizeEdges() {
  return (
    <>
      {ZONES.map((z) => (
        <div
          key={z.edge}
          className={`absolute z-50 ${z.className}`}
          onMouseDown={(e) => {
            if (e.button === 0) {
              e.preventDefault()
              bridge()?.win_resize(z.edge)
            }
          }}
        />
      ))}
    </>
  )
}
