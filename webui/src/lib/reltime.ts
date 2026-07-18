/** Mirrors caspr/timefmt.py so both UIs speak the same language. */
export function relTime(ts: number, nowMs: number = Date.now()): string {
  const delta = Math.max(0, nowMs / 1000 - ts)
  if (delta < 45) return 'just now'
  if (delta < 3600) return `${Math.max(1, Math.floor(delta / 60))} min ago`
  if (delta < 86400) return `${Math.floor(delta / 3600)} h ago`
  const then = new Date(ts * 1000)
  const now = new Date(nowMs)
  const startOfDay = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime()
  const daysApart = Math.round((startOfDay(now) - startOfDay(then)) / 86400000)
  if (daysApart === 1) {
    const hh = String(then.getHours()).padStart(2, '0')
    const mm = String(then.getMinutes()).padStart(2, '0')
    return `yesterday ${hh}:${mm}`
  }
  if (daysApart < 7) return `${daysApart} days ago`
  return `${then.getDate()} ${then.toLocaleString('en', { month: 'short' })}`
}
