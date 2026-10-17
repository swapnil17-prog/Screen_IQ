import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { AlertTriangle, EyeOff, FileWarning, Scale, ShieldCheck } from 'lucide-react'
import { api } from '@/lib/api'
import { timeAgo, titleCase } from '@/lib/format'
import { PageHeader } from '@/components/layout/AppShell'
import { Card, CardBody, CardHeader, StatCard } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { ButtonLink } from '@/components/ui/button'
import { EmptyState, PageLoader } from '@/components/ui/misc'
import { BarList } from '@/components/charts/charts'

const RATING_TONE = { inclusive: 'good', needs_review: 'warn', biased: 'bad' } as const

export function FairnessPage() {
  const { data, isLoading } = useQuery({ queryKey: ['fairness'], queryFn: api.fairness })
  if (isLoading || !data) return <PageLoader />
  const redactionTotal = Object.values(data.redactions).reduce((a, b) => a + b, 0)

  return (
    <>
      <PageHeader
        title="Fairness & compliance"
        description="Bias safeguards across the pipeline: inclusive job posts, blind screening, and counterfactual audits of AI decisions."
        actions={<ButtonLink to="/app/settings" variant="secondary">Fairness settings</ButtonLink>}
      />

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatCard
          label="Blind screening"
          value={data.blind_screening ? 'On' : 'Off'}
          icon={<EyeOff />}
          hint={`${data.screenings_blind} screenings with identity redacted`}
        />
        <StatCard label="Avg. job inclusivity" value={data.avg_inclusivity === null ? '—' : Math.round(data.avg_inclusivity)} icon={<Scale />} hint="0–100, higher is more inclusive" />
        <StatCard
          label="Evaluations audited"
          value={data.evaluations_total}
          icon={<ShieldCheck />}
          hint={data.avg_abs_delta === null ? 'Counterfactual masked vs. unmasked' : `Avg. |delta| ${data.avg_abs_delta.toFixed(1)} pts`}
        />
        <StatCard
          label="Needs human review"
          value={data.evaluations_flagged}
          icon={<AlertTriangle />}
          hint={`Delta above ±${data.bias_delta_threshold} pts`}
        />
      </div>

      {!data.blind_screening && (
        <div className="mt-3 flex items-center gap-2 rounded-lg bg-warn-soft px-4 py-3 text-sm text-warn-text">
          <AlertTriangle className="size-4 shrink-0" /> Blind screening is off: candidate identity is visible to the AI during screening and evaluation.
        </div>
      )}

      <div className="mt-6 grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader title="Job description inclusivity" description="Gender-coded, age, ableist and exclusionary language per open job" />
          {data.jobs.length === 0 ? <CardBody><p className="text-sm text-fg-3">No jobs yet.</p></CardBody> : (
            <ul className="divide-y divide-line border-t border-line">
              {data.jobs.map((j) => (
                <li key={j.job_id}>
                  <Link to={`/app/jobs/${j.job_id}`} className="flex items-center gap-3 px-5 py-3 hover:bg-surface-2">
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-sm font-medium text-fg">{j.title}</div>
                      <div className="text-xs text-fg-3">
                        {j.flags} issue{j.flags === 1 ? '' : 's'}{j.high_severity ? ` · ${j.high_severity} high severity` : ''} · {j.gender_lean} tone
                      </div>
                    </div>
                    <Badge tone={RATING_TONE[j.rating]}>{titleCase(j.rating)} · {j.score}</Badge>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card>
          <CardHeader title="Identity signals redacted" description="Removed before resume evidence reached the AI (blind screening)" />
          <CardBody>
            {redactionTotal === 0 ? <p className="text-sm text-fg-3">Nothing redacted yet.</p> : (
              <BarList data={Object.entries(data.redactions).map(([k, v]) => ({ key: k, label: titleCase(k), value: v }))} />
            )}
            <p className="mt-4 text-xs text-fg-3">
              Includes names, contact details, links, gendered pronouns, age & family-status markers, nationality/religion statements, institutions and locations.
            </p>
          </CardBody>
        </Card>

        <Card>
          <CardHeader title="Counterfactual audit results" description="Each interview is graded with and without identity; large gaps indicate sensitivity to demographic proxies" />
          <CardBody>
            {data.evaluations_total === 0 ? <p className="text-sm text-fg-3">No evaluations yet.</p> : (
              <div className="grid grid-cols-3 gap-3">
                {(['low', 'medium', 'high'] as const).map((r) => (
                  <div key={r} className="rounded-lg border border-line bg-surface-2 p-3 text-center">
                    <div className="text-xl font-semibold text-fg tabular">{data.risk_counts[r] ?? 0}</div>
                    <Badge tone={r === 'low' ? 'good' : r === 'medium' ? 'warn' : 'bad'} className="mt-1">{titleCase(r)} risk</Badge>
                  </div>
                ))}
              </div>
            )}
            {data.flagged_evaluations.length > 0 && (
              <ul className="mt-4 divide-y divide-line rounded-lg border border-line">
                {data.flagged_evaluations.map((f) => (
                  <li key={f.application_id}>
                    <Link to={`/app/applications/${f.application_id}`} className="flex items-center gap-3 px-3 py-2.5 text-sm hover:bg-surface-2">
                      <span className="min-w-0 flex-1 truncate text-fg">{f.candidate_name ?? 'Candidate'} · <span className="text-fg-3">{f.job_title}</span></span>
                      <span className="text-xs text-fg-3 tabular">{f.delta > 0 ? '+' : ''}{f.delta.toFixed(1)} · {timeAgo(f.created_at)}</span>
                      <Badge tone={f.risk === 'high' ? 'bad' : 'warn'}>{titleCase(f.risk)}</Badge>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </CardBody>
        </Card>

        <Card>
          <CardHeader title="Integrity signals" />
          <CardBody className="space-y-3">
            <div className="flex items-start gap-3 rounded-lg border border-line bg-surface-2 p-3">
              <FileWarning className="mt-0.5 size-4 shrink-0 text-warn" />
              <div>
                <div className="text-sm font-medium text-fg">{data.injection_flags} resume{data.injection_flags === 1 ? '' : 's'} with suspected prompt injection</div>
                <p className="mt-0.5 text-xs text-fg-3">Text addressed to AI screeners (e.g. “ignore previous instructions”) is flagged for manual review and never followed.</p>
              </div>
            </div>
            <ul className="space-y-2 text-[13px] text-fg-2">
              <li>• Employment gaps are displayed for context only and are excluded from scoring.</li>
              <li>• Interview questions are generated under rules that forbid protected-characteristic topics.</li>
              <li>• Every screening and evaluation stores a full explainability trace and audit-log entry.</li>
              <li>• AI output is decision support — final hiring decisions stay with your team.</li>
            </ul>
          </CardBody>
        </Card>
      </div>
      {data.jobs.length === 0 && data.evaluations_total === 0 && (
        <Card className="mt-4"><EmptyState icon={<Scale />} title="Fairness data appears as you hire" description="Create jobs and screen candidates to populate this report." /></Card>
      )}
    </>
  )
}
