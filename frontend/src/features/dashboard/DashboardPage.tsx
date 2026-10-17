import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowRight, Loader, Plus, ShieldAlert, Sparkles } from 'lucide-react'
import { api } from '@/lib/api'
import type { Metric } from '@/lib/types'
import { duration } from '@/lib/format'
import { useSession } from '@/hooks/useAuth'
import { PageHeader } from '@/components/layout/AppShell'
import { Card } from '@/components/ui/card'
import { ButtonLink } from '@/components/ui/button'
import { Avatar, EmptyState, PageLoader, Skeleton } from '@/components/ui/misc'
import { Segmented } from '@/components/ui/tabs'
import { PipelineBar, TierLegend } from '@/components/ui/tier'

const RANGES = [
  { key: '1', label: 'Today' },
  { key: '7', label: '7 days' },
  { key: '30', label: '30 days' },
] as const
type Range = (typeof RANGES)[number]['key']

function Delta({ text }: { text: string | null }) {
  if (!text) return null
  return <span className="rounded-md bg-brand-soft px-1.5 py-0.5 text-xs font-semibold text-brand-text tabular">{text}</span>
}

function KpiCard({ label, value, delta, hint }: { label: string; value: string; delta: string | null; hint: string }) {
  return (
    <Card className="px-5 py-5">
      <div className="text-sm text-fg-2">{label}</div>
      <div className="mt-3 flex items-center gap-2.5">
        <span className="text-[32px] font-semibold leading-none tracking-[-0.03em] text-fg tabular">{value}</span>
        <Delta text={delta} />
      </div>
      <div className="mt-3 text-xs text-fg-3">{hint}</div>
    </Card>
  )
}

const signed = (n: number, suffix = '') => `${n > 0 ? '+' : n < 0 ? '−' : '±'}${Math.abs(n).toLocaleString()}${suffix}`

function pctDelta(m: Metric): string | null {
  if (m.value === null || m.previous === null) return null
  if (!m.previous) return m.value ? 'new' : null
  return signed(Math.round(((m.value - m.previous) / m.previous) * 100), '%')
}

export function DashboardPage() {
  const { user } = useSession()
  const [range, setRange] = useState<Range>('7')
  const days = Number(range)
  const { data, isLoading, isFetching } = useQuery({
    queryKey: ['dashboard', days],
    queryFn: () => api.dashboard(days),
    refetchInterval: 30_000,
    placeholderData: (prev) => prev,
  })
  const { data: jobs } = useQuery({
    queryKey: ['jobs', 'open'],
    queryFn: () => api.jobs({ status: 'open' }),
    refetchInterval: (q) => (q.state.data?.some((j) => j.counts.processing > 0) ? 4000 : 30_000),
  })

  const hour = new Date().getHours()
  const greeting = hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening'

  if (isLoading || !data) return <PageLoader />
  const p = data.period
  const k = data.kpis
  const periodLabel = days === 1 ? 'today' : `in the last ${days} days`
  const processing = (jobs ?? []).filter((j) => j.counts.processing > 0)
  const roles = [...(jobs ?? [])].sort((a, b) => b.counts.total - a.counts.total).slice(0, 6)

  return (
    <>
      <PageHeader
        title={`${greeting}, ${user.full_name.split(' ')[0]}`}
        description={
          <>
            {p.screened.value ?? 0} resume{p.screened.value === 1 ? ' was' : 's were'} screened {periodLabel}.{' '}
            {data.needs_review_total > 0 ? `${data.needs_review_total} need your review.` : 'Nothing is waiting for review.'}
          </>
        }
        actions={<Segmented items={[...RANGES]} value={range} onChange={setRange} className={isFetching ? 'opacity-70' : ''} />}
      />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard label="Resumes screened" value={(p.screened.value ?? 0).toLocaleString()} delta={pctDelta(p.screened)}
                 hint={`vs. previous ${days === 1 ? 'day' : `${days} days`}`} />
        <KpiCard label="Avg. match score" value={p.avg_score.value === null ? '—' : String(Math.round(p.avg_score.value))}
                 delta={p.avg_score.delta === null ? null : signed(Math.round(p.avg_score.delta), ' pts')}
                 hint={`Across ${k.open_jobs} open role${k.open_jobs === 1 ? '' : 's'}`} />
        <KpiCard label="Shortlisted" value={String(p.shortlisted.value ?? 0)}
                 delta={p.shortlisted.delta ? signed(p.shortlisted.delta) : null}
                 hint={p.screened.value ? `${((100 * (p.shortlisted.value ?? 0)) / p.screened.value).toFixed(1)}% shortlist rate` : 'Moved to shortlist by your team'} />
        <KpiCard label="Avg. time to screen" value={duration(p.avg_seconds_to_screen.value)}
                 delta={p.avg_seconds_to_screen.delta ? `${p.avg_seconds_to_screen.delta < 0 ? '−' : '+'}${duration(p.avg_seconds_to_screen.delta)}` : null}
                 hint="Upload to scored, per resume" />
      </div>

      {k.flagged_evaluations > 0 && (
        <Link to="/app/fairness" className="mt-4 flex items-center gap-3 rounded-xl border border-[color-mix(in_oklab,var(--bad)_30%,transparent)] bg-bad-soft px-4 py-3 text-sm text-bad-text">
          <ShieldAlert className="size-4 shrink-0" />
          <span className="flex-1"><strong>{k.flagged_evaluations}</strong> evaluation{k.flagged_evaluations > 1 ? 's' : ''} exceeded the bias-sensitivity threshold and need human review.</span>
          <ArrowRight className="size-4" />
        </Link>
      )}

      <div className="mt-6 grid items-start gap-5 xl:grid-cols-[1fr_340px]">
        <Card className="overflow-hidden">
          <div className="flex items-center justify-between px-6 py-5">
            <h2 className="text-lg font-semibold tracking-[-0.01em] text-fg">Active roles</h2>
            <Link to="/app/jobs" className="text-sm font-semibold text-brand-text hover:underline">View all jobs</Link>
          </div>
          {!jobs ? (
            <div className="space-y-3 px-6 pb-6">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-12" />)}</div>
          ) : roles.length === 0 ? (
            <EmptyState className="border-t border-line" icon={<Sparkles />} title="No open roles yet"
                        description="Create a job, drop in resumes, and get a ranked list with evidence for every score."
                        action={<ButtonLink to="/app/jobs/new"><Plus /> Create a job</ButtonLink>} />
          ) : (
            <>
              <div className="overflow-x-auto">
                <table className="w-full text-left">
                  <thead>
                    <tr className="border-y border-line bg-surface-2 text-[13px] text-fg-3">
                      <th className="px-6 py-3 font-medium">Role</th>
                      <th className="px-4 py-3 font-medium">Applicants</th>
                      <th className="px-4 py-3 font-medium">Pipeline</th>
                      <th className="whitespace-nowrap px-6 py-3 font-medium">Top match</th>
                    </tr>
                  </thead>
                  <tbody>
                    {roles.map((j) => (
                      <tr key={j.id} className="border-b border-line last:border-0 hover:bg-surface-2">
                        <td className="px-6 py-4">
                          <Link to={`/app/jobs/${j.id}`} className="block">
                            <div className="text-[15px] font-semibold text-fg hover:text-brand-text">{j.title}</div>
                            <div className="mt-0.5 text-[13px] text-fg-3">{[j.department, j.location, j.employment_type].filter(Boolean).join(' · ') || 'No details'}</div>
                          </Link>
                        </td>
                        <td className="px-4 py-4 text-[15px] text-fg tabular">{j.counts.total}</td>
                        <td className="px-4 py-4"><PipelineBar strong={j.counts.strong} review={j.counts.review} low={j.counts.low} /></td>
                        <td className="px-6 py-4">
                          {j.top_score !== null
                            ? <span className="rounded-md bg-brand-soft px-2 py-1 text-sm font-semibold text-brand-text tabular">{Math.round(j.top_score)}</span>
                            : <span className="text-xs text-fg-3">—</span>}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <TierLegend className="border-t border-line px-6 py-4" />
            </>
          )}
        </Card>

        <div className="space-y-5">
          <Card className="overflow-hidden">
            <div className="flex items-center justify-between px-5 py-5">
              <h2 className="text-lg font-semibold tracking-[-0.01em] text-fg">Needs your review</h2>
              {data.needs_review_total > 0 && (
                <span className="rounded-md bg-tier-low-soft px-2 py-0.5 text-xs font-semibold text-tier-low-text tabular">{data.needs_review_total}</span>
              )}
            </div>
            {data.needs_review.length === 0 ? (
              <p className="border-t border-line px-5 py-6 text-sm text-fg-3">You’re all caught up. Borderline candidates will appear here.</p>
            ) : (
              <ul className="divide-y divide-line border-t border-line">
                {data.needs_review.map((r) => (
                  <li key={r.application_id}>
                    <Link to={`/app/applications/${r.application_id}`} className="flex items-center gap-3 px-5 py-3.5 hover:bg-surface-2">
                      <Avatar name={r.candidate_name} className="bg-surface-3 text-fg-2" />
                      <div className="min-w-0 flex-1">
                        <div className="truncate text-[15px] font-semibold text-fg">{r.candidate_name ?? 'Unnamed candidate'}</div>
                        <div className="truncate text-[13px] text-fg-3">{r.reason ?? r.job_title}</div>
                      </div>
                      <span className="text-[15px] font-semibold text-fg tabular">{Math.round(r.score)}</span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </Card>

          <div className="rounded-xl bg-ink p-5 text-ink-fg">
            {processing.length > 0 ? (
              <>
                <div className="flex items-center gap-2 text-[15px] font-semibold"><Loader className="size-4 animate-spin" />Screening in progress</div>
                <div className="mt-3 space-y-3">
                  {processing.slice(0, 3).map((j) => {
                    const done = j.counts.total - j.counts.processing
                    return (
                      <div key={j.id}>
                        <div className="text-sm text-ink-fg/80">{j.title} · {done} of {j.counts.total} resumes screened</div>
                        <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-white/10">
                          <div className="h-full rounded-full bg-[#a4a5ef] transition-[width] duration-500" style={{ width: `${(done / j.counts.total) * 100}%` }} />
                        </div>
                      </div>
                    )
                  })}
                </div>
                <p className="mt-3 text-xs text-ink-fg/55">Scores appear in each role’s ranked list as they finish.</p>
              </>
            ) : (
              <>
                <div className="flex items-center gap-2 text-[15px] font-semibold"><Sparkles className="size-4" />AI interviews</div>
                <p className="mt-2 text-sm text-ink-fg/80">
                  {k.interviews_active} in progress · {k.interviews_completed} completed · {k.evaluations} evaluated
                </p>
                <Link to="/app/interviews" className="mt-3 inline-flex items-center gap-1 text-sm font-semibold text-[#c7c8ff] hover:underline">
                  Open interviews <ArrowRight className="size-3.5" />
                </Link>
              </>
            )}
          </div>
        </div>
      </div>
    </>
  )
}
