import { useState } from 'react'
import { BadgeCheck, CheckCircle2, ChevronDown, CircleDashed, Quote, ShieldQuestion, XCircle } from 'lucide-react'
import type { RequirementAssessment } from '@/lib/types'
import { titleCase } from '@/lib/format'
import { cn } from '@/lib/utils'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Segmented } from '@/components/ui/tabs'

const VERDICT = {
  met: { icon: CheckCircle2, label: 'Met', cls: 'text-good-text' },
  partial: { icon: CircleDashed, label: 'Partial', cls: 'text-warn-text' },
  not_met: { icon: XCircle, label: 'Not met', cls: 'text-bad-text' },
}

function Requirement({ r }: { r: RequirementAssessment }) {
  const [open, setOpen] = useState(false)
  const v = VERDICT[r.verdict]
  return (
    <li className="border-t border-line first:border-t-0">
      <button onClick={() => setOpen(!open)} aria-expanded={open} className="flex w-full items-start gap-3 px-5 py-4 text-left transition-colors hover:bg-surface-2">
        <v.icon className={cn('mt-0.5 size-4 shrink-0', v.cls)} />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-medium text-fg">{r.requirement}</span>
            <span className={cn('text-xs font-medium', v.cls)}>{v.label}</span>
            <Badge>{titleCase(r.kind)}</Badge>
            {r.importance === 'nice_to_have' && <Badge>Nice to have</Badge>}
          </div>
          <p className="mt-1 text-[13px] text-fg-2">{r.reasoning}</p>
          {r.evidence_quote && (
            <div className="mt-2 flex items-start gap-2 rounded-lg border-l-2 border-brand bg-brand-soft/60 px-3 py-2">
              <Quote className="mt-0.5 size-3.5 shrink-0 text-brand-text" />
              <p className="flex-1 text-[13px] italic text-fg">“{r.evidence_quote}”</p>
              {r.quote_verified ? (
                <span className="inline-flex shrink-0 items-center gap-1 text-[11px] font-medium text-good-text" title="Quote found verbatim in the resume">
                  <BadgeCheck className="size-3.5" /> Verified
                </span>
              ) : (
                <span className="inline-flex shrink-0 items-center gap-1 text-[11px] font-medium text-warn-text" title="Quote couldn't be matched to the resume text — treat with caution">
                  <ShieldQuestion className="size-3.5" /> Unverified
                </span>
              )}
            </div>
          )}
        </div>
        <ChevronDown className={cn('mt-0.5 size-4 shrink-0 text-fg-3 transition-transform', open && 'rotate-180')} />
      </button>
      {open && (
        <div className="space-y-2 px-5 pb-4 pl-12">
          <div className="text-[11px] font-semibold uppercase tracking-wide text-fg-3">Retrieved resume evidence (top {r.evidence.length} by vector similarity)</div>
          {r.evidence.map((e) => (
            <div key={e.id} className="rounded-lg border border-line bg-surface-2 p-3">
              <div className="mb-1.5 flex items-center justify-between text-[11px] text-fg-3">
                <span className="font-medium uppercase tracking-wide">{e.section}</span>
                <span className="tabular">cosine {e.similarity.toFixed(3)}</span>
              </div>
              <p className="whitespace-pre-wrap text-[13px] leading-relaxed text-fg-2">{e.text}</p>
            </div>
          ))}
          {r.evidence.length === 0 && <p className="text-xs text-fg-3">No matching resume excerpts were retrieved.</p>}
        </div>
      )}
    </li>
  )
}

export function EvidencePanel({ requirements }: { requirements: RequirementAssessment[] }) {
  const [filter, setFilter] = useState<'all' | 'met' | 'partial' | 'not_met'>('all')
  const shown = requirements.filter((r) => filter === 'all' || r.verdict === filter)
  const count = (k: string) => requirements.filter((r) => r.verdict === k).length
  const verified = requirements.filter((r) => r.evidence_quote && r.quote_verified).length
  const quoted = requirements.filter((r) => r.evidence_quote).length
  return (
    <Card>
      <div className="flex flex-col gap-3 border-b border-line px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h3 className="text-[14px] font-semibold text-fg">Requirement-by-requirement evidence</h3>
          <p className="mt-0.5 text-[13px] text-fg-3">
            RAG: each requirement retrieves the most similar resume chunks from pgvector; the AI judges them and cites a quote.
            {quoted > 0 && ` ${verified}/${quoted} quotes verified.`}
          </p>
        </div>
        <Segmented
          value={filter}
          onChange={setFilter}
          items={[
            { key: 'all', label: `All ${requirements.length}` },
            { key: 'met', label: `Met ${count('met')}` },
            { key: 'partial', label: `Partial ${count('partial')}` },
            { key: 'not_met', label: `Not met ${count('not_met')}` },
          ]}
        />
      </div>
      <ul>{shown.map((r) => <Requirement key={r.id} r={r} />)}</ul>
      {shown.length === 0 && <p className="px-5 py-8 text-center text-sm text-fg-3">No requirements in this category.</p>}
    </Card>
  )
}
