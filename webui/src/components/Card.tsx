export function Card({
  className = '',
  children,
}: {
  className?: string
  children: React.ReactNode
}) {
  return (
    <div className={`rounded-[18px] border border-hairline bg-surface shadow-[0_2px_12px_rgba(0,0,0,0.06)] ${className}`}>
      {children}
    </div>
  )
}
