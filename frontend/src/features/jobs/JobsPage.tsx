import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Briefcase, MapPin, Plus, Search, Users } from 'lucide-react'
import { api } from '@/lib/api'
import { score, timeAgo } from '@/lib/format'
import { useAuth } from '@/hooks/useAuth'
import { PageHeader } from '@/components/layout/AppShell'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { ButtonLink } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Segmented } from '@/components/ui/tabs'
import { EmptyState, PageLoader, Spinner } from '@/components/ui/misc'
import type { JobSummary } from '@/lib/types'

const STATUS_TONE = { open: 'good', paused: 'warn', closed: 'neutral', archived: 'neutral' } as const

function JobCard({ job }: { job: JobSummary }) {
  const c = job.counts
  return (
    <Link to={`/app/jobs/${job.id}`} className="group">
      <Card className="flex h-full flex-col p-5 transition-[box-shadow,border-color] group-hover:border-line-strong group-hover:shadow-pop">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h3 className="truncate text-[15px] font-semibold text-fg group-hover:text-brand-text">{job.title}</h3>
            <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-fg-3">
              {job.department && <span>{job.department}</span>}
              {job.location && <span className="inline-flex items-center gap-1"><MapPin className="size-3" />{job.location}</span>}
              <span>Created {timeAgo(job.created_at)}</span>
            </div>
          </div>
          <Badge tone={STATUS_TONE[job.status]} dot>{job.status}</Badge>
        </div>

        <div className="mt-5 grid grid-cols-3 gap-3 border-t border-line pt-4">
          <div>
            <div className="text-[11px] font-medium uppercase tracking-wide text-fg-3">Candidates</div>
            <div className="mt-1 flex items-center gap-1.5 text-lg font-semibold text-fg tabular">
              {c.total}
              {c.processing > 0 && <Spinner className="size-3.5 text-brand" />}
            </div>
          </div>
          <div>
            <div className="text-[11px] font-medium uppercase tracking-wide text-fg-3">Avg score</div>
            <div className="mt-1 text-lg font-semibold text-fg tabular">{score(job.avg_score)}</div>
          </div>
          <div>
            <div className="text-[11px] font-medium uppercase tracking-wide text-fg-3">Interviewing</div>
            <div className="mt-1 text-lg font-semibold text-fg tabular">{c.interviewing}</div>
          </div>
        </div>
        <div className="mt-4 flex flex-wrap items-center gap-2 text-xs">
          {job.extraction_status === 'pending' && <Badge tone="brand" icon={<Spinner className="size-3" />}>Analyzing JD</Badge>}
          {job.extraction_status === 'failed' && <Badge tone="bad">JD analysis failed</Badge>}
          {job.inclusivity_score !== null && (
            <Badge tone={job.inclusivity_score >= 85 ? 'good' : job.inclusivity_score >= 65 ? 'warn' : 'bad'}>
              Inclusivity {job.inclusivity_score}
            </Badge>
          )}
          {c.failed > 0 && <Badge tone="bad">{c.failed} failed</Badge>}
        </div>
      </Card>
    </Link>
  )
}

export function JobsPage() {
  const { can } = useAuth()
  const [status, setStatus] = useState<'open' | 'all'>('open')
  const [q, setQ] = useState('')
  const { data, isLoading } = useQuery({
    queryKey: ['jobs', status],
    queryFn: () => api.jobs(status === 'open' ? { status: 'open' } : {}),
    refetchInterval: (query) =>
      query.state.data?.some((j) => j.counts.processing > 0 || j.extraction_status === 'pending') ? 4000 : false,
  })
  const jobs = (data ?? []).filter((j) => !q || `${j.title} ${j.department ?? ''} ${j.location ?? ''}`.toLowerCase().includes(q.toLowerCase()))

  return (
    <>
      <PageHeader
        title="Jobs"
        description="Every role you're hiring for, with live screening progress."
        actions={can('write') && <ButtonLink to="/app/jobs/new"><Plus /> New job</ButtonLink>}
      />
      <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative sm:w-72">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-fg-3" />
          <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Filter jobs…" className="pl-9" aria-label="Filter jobs" />
        </div>
        <Segmented items={[{ key: 'open', label: 'Open' }, { key: 'all', label: 'All jobs' }]} value={status} onChange={setStatus} />
      </div>

      {isLoading ? (
        <PageLoader />
      ) : jobs.length === 0 ? (
        <Card>
          <EmptyState
            icon={q ? <Search /> : <Briefcase />}
            title={q ? 'No jobs match your filter' : 'No jobs yet'}
            description={q ? 'Try a different search.' : 'Create a job to start screening candidates against its requirements.'}
            action={!q && can('write') && <ButtonLink to="/app/jobs/new"><Plus /> Create a job</ButtonLink>}
          />
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {jobs.map((j) => <JobCard key={j.id} job={j} />)}
        </div>
      )}
      {!isLoading && jobs.length > 0 && (
        <p className="mt-4 flex items-center gap-1.5 text-xs text-fg-3"><Users className="size-3.5" /> {jobs.reduce((a, j) => a + j.counts.total, 0)} candidates across {jobs.length} job{jobs.length === 1 ? '' : 's'}</p>
      )}
    </>
  )
}
