/** Renders dictated text with unknown-word spans marked in ember. */
export function FlaggedText({ text, spans }: { text: string; spans: [number, number][] }) {
  if (!spans.length) return <>{text}</>
  const parts: React.ReactNode[] = []
  let prev = 0
  spans.forEach(([start, end], i) => {
    if (start > prev) parts.push(text.slice(prev, start))
    parts.push(
      <span key={i} className="text-ember underline decoration-ember/50 underline-offset-2">
        {text.slice(start, end)}
      </span>,
    )
    prev = end
  })
  if (prev < text.length) parts.push(text.slice(prev))
  return <>{parts}</>
}
