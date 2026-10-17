import { AlertTriangle, CheckCircle2, Info, ShieldCheck } from 'lucide-react'
import type { JDBiasReport } from '@/lib/types'
import { titleCase } from '@/lib/format'
import { cn } from '@/lib/utils'
import { Badge } from '@/components/ui/badge'

const RATING = {
  inclusive: { label: 'Inclusive', tone: 'good' as const, icon: <CheckCircle2 /> },
  needs_review: { label: 'Needs review', tone: 'warn' as const, icon: <AlertTriangle /> },
  biased: { label: 'Likely biased', tone: 'bad' as const, icon: <AlertTriangle /> },
}

const SEVERITY = { high: 'bad', medium: 'warn', low: 'neutral' } as const

export function InclusivityBadge({ report }: { report: JDBiasReport | null | undefined }) {
  if (!report) return null
  const r = RATING[report.rating]
  return (
    <Badge tone={r.tone} icon={r.icon}>
      {r.label} · {report.score}
    </Badge>
  )
}

export function BiasReport({ report, compact }: { report: JDBiasReport; compact?: boolean }) {
  const r = RATING[report.rating]
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-4">
        <div
          className={cn(
            'flex size-14 shrink-0 flex-col items-center justify-center rounded-xl border',
            r.tone === 'good' && 'border-[color-mix(in_oklab,var(--good)_30%,transparent)] bg-good-soft text-good-text',
            r.tone === 'warn' && 'border-[color-mix(in_oklab,var(--warn)_40%,transparent)] bg-warn-soft text-warn-text',
            r.tone === 'bad' && 'border-[color-mix(in_oklab,var(--bad)_30%,transparent)] bg-bad-soft text-bad-text',
          )}
        >
          <span className="text-lg font-semibold leading-none tabular">{report.score}</span>
          <span className="mt-0.5 text-[9px] font-medium uppercase tracking-wider">/ 100</span>
        </div>
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold text-fg">Inclusivity: {r.label}</span>
          </div>
          <p className="mt-0.5 text-[13px] text-fg-2">{report.summary}</p>
          {!compact && (
            <p className="mt-1 text-xs text-fg-3">
              Gender-coded words: {report.masculine_count} masculine · {report.feminine_count} feminine
            </p>
          )}
        </div>
      </div>

      {report.flags.length === 0 ? (
        <div className="flex items-center gap-2 rounded-lg border border-line bg-surface-2 px-3 py-2.5 text-[13px] text-fg-2">
          <ShieldCheck className="size-4 text-good" /> No exclusionary language found.
        </div>
      ) : (
        <ul className="space-y-2">
          {report.flags.map((f, i) => (
            <li key={`${f.category}-${i}`} className="rounded-lg border border-line bg-surface-2 p-3">
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone={SEVERITY[f.severity]} dot>{titleCase(f.severity)}</Badge>
                <span className="text-xs font-medium text-fg-3">{titleCase(f.category)}</span>
                <code className="rounded bg-surface-3 px-1.5 py-0.5 font-mono text-xs text-fg">“{f.phrase}”</code>
                {f.count > 1 && <span className="text-xs text-fg-3">×{f.count}</span>}
              </div>
              <p className="mt-1.5 flex gap-1.5 text-[13px] text-fg-2">
                <Info className="mt-0.5 size-3.5 shrink-0 text-fg-3" />
                {f.suggestion}
              </p>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
