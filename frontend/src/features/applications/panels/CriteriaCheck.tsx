import { Check, X } from 'lucide-react'
import type { RequirementAssessment } from '@/lib/types'
import { cn } from '@/lib/utils'
import { Card } from '@/components/ui/card'

function Mark({ verdict }: { verdict: RequirementAssessment['verdict'] }) {
  if (verdict === 'met') {
    return <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-brand text-brand-fg" aria-label="Met"><Check className="size-3.5" strokeWidth={3} /></span>
  }
  if (verdict === 'partial') {
    return <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-tier-low-soft text-sm font-bold text-tier-low-text" aria-label="Partially met">~</span>
  }
  return <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-tier-low-soft text-tier-low-text" aria-label="Not met"><X className="size-3.5" strokeWidth={3} /></span>
}

function clip(s: string, n = 70) {
  return s.length > n ? `${s.slice(0, n).trimEnd()}…` : s
}

export function CriteriaCheck({ requirements }: { requirements: RequirementAssessment[] }) {
  const ordered = [...requirements].sort((a, b) => (a.importance === b.importance ? 0 : a.importance === 'required' ? -1 : 1))
  return (
    <Card className="flex h-full flex-col">
      <h3 className="px-5 pb-2 pt-5 text-lg font-semibold tracking-[-0.01em] text-fg">Criteria check</h3>
      <ul className="flex-1 divide-y divide-line px-5 pb-3">
        {ordered.map((r) => (
          <li key={r.id} className="flex items-start gap-3 py-3">
            <Mark verdict={r.verdict} />
            <div className="min-w-0 flex-1">
              <div className={cn('text-[15px] font-medium', r.verdict === 'not_met' ? 'text-fg-2' : 'text-fg')}>{r.requirement}</div>
              <div className="mt-0.5 text-[13px] text-fg-3" title={r.evidence_quote ?? r.reasoning}>
                {clip(r.evidence_quote ?? r.reasoning)}
              </div>
            </div>
            <span className="shrink-0 pt-1 text-[11px] font-semibold tracking-wide text-fg-3">{r.importance === 'required' ? 'MUST' : 'NICE'}</span>
          </li>
        ))}
        {ordered.length === 0 && <li className="py-4 text-sm text-fg-3">No criteria assessed.</li>}
      </ul>
    </Card>
  )
}
