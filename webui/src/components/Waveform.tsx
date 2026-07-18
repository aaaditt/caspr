const BARS = 28
const IDLE_HEIGHTS = [38, 62, 45, 80, 55, 70, 42, 88, 50, 66, 58, 76, 40, 84]

/** Ember VU meter. `levels` (0..1 per bar, newest last) drives it live;
 *  with no levels it breathes gently — the app's heartbeat. */
export function Waveform({
  levels,
  animated = true,
}: {
  levels?: number[]
  animated?: boolean
}) {
  return (
    <div className="flex h-7 items-center gap-[3px]" aria-hidden>
      {Array.from({ length: BARS }, (_, i) => {
        const live = levels && levels.length > 0
        const height = live
          ? `${8 + Math.min(1, levels![Math.max(0, levels!.length - BARS + i)] ?? 0) * 92}%`
          : undefined
        return (
          <span
            key={i}
            className="w-[3px] rounded-full bg-gradient-to-b from-coral to-amber"
            style={
              live
                ? { height, transition: 'height 90ms ease-out' }
                : {
                    ['--h' as string]: `${IDLE_HEIGHTS[i % IDLE_HEIGHTS.length]}%`,
                    height: '26%',
                    animation: animated
                      ? `wave-bob 1.3s ease-in-out ${i * 0.09}s infinite`
                      : undefined,
                  }
            }
          />
        )
      })}
    </div>
  )
}
