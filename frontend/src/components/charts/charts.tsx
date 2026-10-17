/**
 * Minimal, theme-aware charts in plain HTML/CSS.
 * - Magnitude uses one hue (sequential blue); identity uses the validated
 *   categorical order (--s1..--s4). Values are always printed as text so
 *   identity/magnitude never depends on color alone.
 */
import { useState } from 'react'
import { cn } from '@/lib/utils'

export interface Datum {
  key: string
  label: string
  value: number
  hint?: string
}

/** Horizontal labelled bars for ranked magnitudes. */
export function BarList({
  data,
  max,
  format = (v) => String(Math.round(v)),
  className,
}: {
  data: Datum[]
  max?: number
  format?: (v: number) => string
  className?: string
}) {
  const top = max ?? Math.max(1, ...data.map((d) => d.value))
  return (
    <ul className={cn('space-y-2.5', className)}>
      {data.map((d) => (
        <li key={d.key} title={d.hint}>
          <div className="mb-1 flex items-baseline justify-between gap-3 text-[13px]">
            <span className="truncate text-fg-2">{d.label}</span>
            <span className="font-medium text-fg tabular">{format(d.value)}</span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-track">
            <div className="h-full rounded-full bg-seq-2 transition-[width] duration-700" style={{ width: `${(d.value / top) * 100}%` }} />
          </div>
        </li>
      ))}
    </ul>
  )
}

const SERIES = ['var(--s1)', 'var(--s2)', 'var(--s3)', 'var(--s4)']

/** Stacked 0-100 bar of weighted contributions, with a legend that doubles as the data table. */
export function ContributionBar({
  parts,
  total,
}: {
  parts: { key: string; label: string; contribution: number; score: number; weight: number }[]
  total: number
}) {
  const [hover, setHover] = useState<string | null>(null)
  return (
    <div>
      <div className="flex h-3 w-full overflow-hidden rounded-full bg-track" role="img" aria-label={`Score ${Math.round(total)} of 100`}>
        {parts.map((p, i) => (
          <div
            key={p.key}
            onMouseEnter={() => setHover(p.key)}
            onMouseLeave={() => setHover(null)}
            className={cn('h-full transition-opacity', i > 0 && 'border-l-2 border-surface', hover && hover !== p.key && 'opacity-40')}
            style={{ width: `${p.contribution}%`, background: SERIES[i % SERIES.length] }}
            title={`${p.label}: ${p.contribution.toFixed(1)} pts`}
          />
        ))}
      </div>
      <div className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2 sm:grid-cols-4">
        {parts.map((p, i) => (
          <div
            key={p.key}
            onMouseEnter={() => setHover(p.key)}
            onMouseLeave={() => setHover(null)}
            className={cn('flex items-start gap-2 rounded-md transition-opacity', hover && hover !== p.key && 'opacity-50')}
          >
            <span className="mt-1 size-2.5 shrink-0 rounded-[3px]" style={{ background: SERIES[i % SERIES.length] }} />
            <div className="min-w-0">
              <div className="truncate text-xs text-fg-2">{p.label}</div>
              <div className="text-[13px] font-semibold text-fg tabular">
                +{p.contribution.toFixed(1)} <span className="font-normal text-fg-3">pts</span>
              </div>
              <div className="text-[11px] text-fg-3 tabular">
                {Math.round(p.score)} × {Math.round(p.weight * 100)}%
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

export function seriesColor(i: number) {
  return SERIES[i % SERIES.length]
}
