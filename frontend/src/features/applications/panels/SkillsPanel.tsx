import { CheckCircle2, CircleDashed, XCircle } from 'lucide-react'
import type { SkillGap, SkillMatch } from '@/lib/types'
import { cn } from '@/lib/utils'
import { Card, CardBody, CardHeader } from '@/components/ui/card'
import { Chip } from '@/components/ui/badge'
import { ProgressBar } from '@/components/ui/misc'

const STATUS = {
  matched: { icon: CheckCircle2, label: 'Matched', cls: 'text-good-text' },
  partial: { icon: CircleDashed, label: 'Partial', cls: 'text-warn-text' },
  missing: { icon: XCircle, label: 'Missing', cls: 'text-bad-text' },
}

function how(m: SkillMatch): string {
  switch (m.method) {
    case 'exact': return 'Listed on resume'
    case 'alias': return `Listed as “${m.matched_to}”`
    case 'mentioned': return 'Found in experience text'
    case 'semantic': return `Semantically similar to “${m.matched_to}”${m.similarity ? ` (${m.similarity.toFixed(2)})` : ''}`
    case 'related': return `Related skill: “${m.matched_to}”`
    default: return 'No evidence found'
  }
}

function MatchList({ items }: { items: SkillMatch[] }) {
  return (
    <ul className="divide-y divide-line">
      {items.map((m) => {
        const st = STATUS[m.status]
        return (
          <li key={m.skill} className="flex items-center gap-3 py-2.5">
            <st.icon className={cn('size-4 shrink-0', st.cls)} />
            <span className="min-w-0 flex-1 truncate text-sm font-medium text-fg">{m.skill}</span>
            <span className="hidden truncate text-xs text-fg-3 sm:block">{how(m)}</span>
            <span className={cn('w-16 text-right text-xs font-medium', st.cls)}>{st.label}</span>
          </li>
        )
      })}
    </ul>
  )
}

export function SkillsPanel({ gap }: { gap: SkillGap }) {
  const required = gap.matches.filter((m) => m.importance === 'required')
  const nice = gap.matches.filter((m) => m.importance === 'nice_to_have')
  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-3">
        <Card className="p-4">
          <div className="text-xs text-fg-3">Required coverage</div>
          <div className="mt-1 text-2xl font-semibold text-fg tabular">{Math.round(gap.required_coverage_pct)}%</div>
          <ProgressBar value={gap.required_coverage_pct} tone="seq" className="mt-3" />
        </Card>
        <Card className="p-4">
          <div className="text-xs text-fg-3">Nice-to-have coverage</div>
          <div className="mt-1 text-2xl font-semibold text-fg tabular">{nice.length ? `${Math.round(gap.nice_to_have_coverage_pct)}%` : '—'}</div>
          <ProgressBar value={gap.nice_to_have_coverage_pct} tone="seq" className="mt-3" />
        </Card>
        <Card className="p-4">
          <div className="text-xs text-fg-3">Skill gaps</div>
          <div className="mt-1 text-2xl font-semibold text-fg tabular">{gap.missing_required.length}</div>
          <div className="mt-2 text-xs text-fg-3">required skill{gap.missing_required.length === 1 ? '' : 's'} missing · {gap.partial_required.length} partial</div>
        </Card>
      </div>

      <Card>
        <CardHeader title="Required skills" description="Hybrid matching: exact → alias → in-text mention → embedding similarity → related" />
        <CardBody>{required.length ? <MatchList items={required} /> : <p className="text-sm text-fg-3">The job lists no required skills.</p>}</CardBody>
      </Card>
      {nice.length > 0 && (
        <Card>
          <CardHeader title="Nice-to-have skills" />
          <CardBody><MatchList items={nice} /></CardBody>
        </Card>
      )}
      {gap.missing_required.length > 0 && (
        <Card>
          <CardHeader title="Skill-gap summary" description="Consider probing these in the AI interview (gap-probe questions are generated automatically)" />
          <CardBody className="flex flex-wrap gap-1.5">
            {gap.missing_required.map((s) => <Chip key={s} className="border-[color-mix(in_oklab,var(--bad)_30%,transparent)] bg-bad-soft text-bad-text">{s}</Chip>)}
            {gap.partial_required.map((s) => <Chip key={s} className="border-[color-mix(in_oklab,var(--warn)_40%,transparent)] bg-warn-soft text-warn-text">{s} (partial)</Chip>)}
          </CardBody>
        </Card>
      )}
      {gap.bonus_skills.length > 0 && (
        <Card>
          <CardHeader title="Additional skills" description="Skills on the resume the job didn’t ask for" />
          <CardBody className="flex flex-wrap gap-1.5">
            {gap.bonus_skills.map((s) => <Chip key={s} muted>{s}</Chip>)}
          </CardBody>
        </Card>
      )}
    </div>
  )
}
