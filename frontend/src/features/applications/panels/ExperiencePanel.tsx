import { Info, TrendingUp } from 'lucide-react'
import type { ExperienceAnalysis, ScreeningResult } from '@/lib/types'
import { monthYear, months, titleCase, years } from '@/lib/format'
import { Card, CardBody, CardHeader } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { BarList } from '@/components/charts/charts'

export function ExperiencePanel({ exp, fit }: { exp: ExperienceAnalysis | null; fit: ScreeningResult['experience_fit'] | null }) {
  if (!exp) return <p className="text-sm text-fg-3">No experience data.</p>
  const meets = fit?.required_years && exp.total_years !== null ? exp.total_years >= fit.required_years : null
  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-4">
        {[
          ['Total experience', years(exp.total_years), fit?.required_years ? `${fit.required_years}+ required` : 'No minimum stated'],
          ['Estimated seniority', exp.seniority_estimate ? titleCase(exp.seniority_estimate) : '—', fit?.expected_seniority ? `Role: ${titleCase(fit.expected_seniority)}` : ''],
          ['Average tenure', months(exp.average_tenure_months ? Math.round(exp.average_tenure_months) : null), `${exp.role_count} role${exp.role_count === 1 ? '' : 's'}`],
          ['Career progression', titleCase(exp.progression), exp.current_title ?? ''],
        ].map(([k, v, h]) => (
          <Card key={k} className="p-4">
            <div className="text-xs text-fg-3">{k}</div>
            <div className="mt-1 text-lg font-semibold text-fg">{v}</div>
            <div className="mt-0.5 truncate text-xs text-fg-3">{h}</div>
          </Card>
        ))}
      </div>
      {meets !== null && (
        <p className="px-1 text-[13px] text-fg-2">
          {meets ? '✓ Meets' : '✗ Below'} the minimum experience requirement. Total experience is the union of dated roles — overlapping jobs aren’t double-counted.
        </p>
      )}

      <div className="grid gap-4 lg:grid-cols-[1fr_320px]">
        <Card>
          <CardHeader title="Work history" description="Parsed and analyzed deterministically" />
          <CardBody>
            <ol className="relative space-y-5 border-l border-line pl-5">
              {exp.roles.map((r, i) => (
                <li key={`${r.company}-${i}`} className="relative">
                  <span className={`absolute -left-[25px] top-1.5 size-2.5 rounded-full ring-4 ring-surface ${r.is_current ? 'bg-brand' : 'bg-fg-3'}`} />
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-semibold text-fg">{r.title}</span>
                    {r.seniority && <Badge>{titleCase(r.seniority)}</Badge>}
                    {r.is_current && <Badge tone="brand">Current</Badge>}
                  </div>
                  <div className="mt-0.5 text-[13px] text-fg-2">{r.company}</div>
                  <div className="mt-0.5 text-xs text-fg-3">
                    {r.start ? `${monthYear(r.start)} – ${r.is_current ? 'Present' : monthYear(r.end)}` : 'Dates not specified'}
                    {r.months ? ` · ${months(r.months)}` : ''}
                  </div>
                </li>
              ))}
            </ol>
          </CardBody>
        </Card>
        <div className="space-y-4">
          {fit && fit.relevant_roles.length > 0 && (
            <Card>
              <CardHeader icon={<TrendingUp />} title="Role relevance" description="Embedding similarity of each role to this job" />
              <CardBody>
                <BarList
                  max={100}
                  format={(v) => `${Math.round(v)}%`}
                  data={fit.relevant_roles.map((r) => ({ key: r.title + r.company, label: `${r.title} · ${r.company}`, value: r.relevance }))}
                />
              </CardBody>
            </Card>
          )}
          {(exp.gaps.length > 0 || exp.flags.length > 0) && (
            <Card>
              <CardHeader icon={<Info />} title="Notes" />
              <CardBody className="space-y-2 text-[13px] text-fg-2">
                {exp.gaps.map((g) => (
                  <p key={g.start}>Gap of {months(g.months)} ({monthYear(g.start)} – {monthYear(g.end)})</p>
                ))}
                {exp.flags.map((f) => <p key={f}>{f}</p>)}
                {exp.gaps.length > 0 && (
                  <p className="rounded-md bg-surface-2 p-2 text-xs text-fg-3">
                    Employment gaps often reflect caregiving, health or study. They are shown for context only and never affect the score.
                  </p>
                )}
              </CardBody>
            </Card>
          )}
        </div>
      </div>
    </div>
  )
}
