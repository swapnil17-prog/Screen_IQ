import { cn } from '@/lib/utils'
import { scoreTone, type Tone } from '@/lib/format'

const stroke: Record<Tone, string> = {
  good: 'var(--good)',
  warn: 'var(--warn)',
  bad: 'var(--bad)',
  brand: 'var(--brand)',
  neutral: 'var(--fg-3)',
}

export function ScoreRing({
  value,
  size = 96,
  thickness = 8,
  label,
  tone,
  className,
}: {
  value: number | null | undefined
  size?: number
  thickness?: number
  label?: string
  tone?: Tone
  className?: string
}) {
  const r = (size - thickness) / 2
  const c = 2 * Math.PI * r
  const v = value ?? 0
  const t = tone ?? scoreTone(value)
  return (
    <div className={cn('relative inline-flex shrink-0 items-center justify-center', className)} style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90" aria-hidden>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--track)" strokeWidth={thickness} />
        {value !== null && value !== undefined && (
          <circle
            cx={size / 2}
            cy={size / 2}
            r={r}
            fill="none"
            stroke={stroke[t]}
            strokeWidth={thickness}
            strokeLinecap="round"
            strokeDasharray={c}
            strokeDashoffset={c * (1 - Math.max(0, Math.min(100, v)) / 100)}
            style={{ transition: 'stroke-dashoffset 700ms cubic-bezier(0.16,1,0.3,1)' }}
          />
        )}
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="font-semibold leading-none tracking-[-0.03em] text-fg" style={{ fontSize: size * 0.3 }}>
          {value === null || value === undefined ? '—' : Math.round(v)}
        </span>
        {label && <span className="mt-1 text-[10px] font-medium uppercase tracking-wider text-fg-3">{label}</span>}
      </div>
    </div>
  )
}

const pill: Record<Tone, string> = {
  good: 'bg-good-soft text-good-text',
  warn: 'bg-warn-soft text-warn-text',
  bad: 'bg-bad-soft text-bad-text',
  brand: 'bg-brand-soft text-brand-text',
  neutral: 'bg-surface-3 text-fg-3',
}

export function ScorePill({ value, className }: { value: number | null | undefined; className?: string }) {
  return (
    <span
      className={cn(
        'inline-flex h-7 min-w-10 items-center justify-center rounded-md px-2 text-[13px] font-semibold tabular',
        pill[scoreTone(value)],
        className,
      )}
    >
      {value === null || value === undefined ? '—' : Math.round(value)}
    </span>
  )
}
