import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CircleAlert, FileText, MoreHorizontal, RefreshCw, Scale, SlidersHorizontal, Trash2, Upload } from 'lucide-react'
import { api } from '@/lib/api'
import type { Tier } from '@/lib/types'
import { timeAgo, titleCase } from '@/lib/format'
import { cn, errorMessage } from '@/lib/utils'
import { useAuth } from '@/hooks/useAuth'
import { Card, CardBody, CardHeader } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { EmptyState, PageLoader, Spinner } from '@/components/ui/misc'
import { Menu, MenuItem, MenuLabel } from '@/components/ui/menu'
import { ConfirmDialog } from '@/components/ui/dialog'
import { useToast } from '@/components/ui/toast'
import { CriteriaChip } from '@/components/ui/tier'
import { BiasReport, InclusivityBadge } from './BiasReport'
import { CandidatesTable } from './CandidatesTable'
import { CriteriaDialog } from './CriteriaDialog'
import { RequirementsTab, ScoringTab } from './JobSections'
import { UploadDialog } from './UploadDialog'

type View = 'candidates' | 'details' | 'inclusivity' | 'scoring'

const STATUS_STYLE: Record<string, string> = {
  open: 'bg-brand-soft text-brand-text',
  paused: 'bg-warn-soft text-warn-text',
  closed: 'bg-surface-3 text-fg-3',
  archived: 'bg-surface-3 text-fg-3',
}

export function JobDetailPage() {
  const { jobId = '' } = useParams()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const { can } = useAuth()
  const [view, setView] = useState<View>('candidates')
  const [tier, setTier] = useState<Tier | 'all'>('all')
  const [uploadOpen, setUploadOpen] = useState(false)
  const [criteriaOpen, setCriteriaOpen] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)

  const { data: job, isLoading, error } = useQuery({
    queryKey: ['job', jobId],
    queryFn: () => api.job(jobId),
    refetchInterval: (q) => (q.state.data?.extraction_status === 'pending' || (q.state.data?.counts.processing ?? 0) > 0 ? 3000 : false),
  })

  const setStatus = useMutation({
    mutationFn: (status: string) => api.updateJob(jobId, { status }),
    onSuccess: (j) => { qc.setQueryData(['job', jobId], j); qc.invalidateQueries({ queryKey: ['jobs'] }) },
    onError: (e) => toast.error('Couldn’t update status', errorMessage(e)),
  })
  const rescore = useMutation({
    mutationFn: () => api.rescoreJob(jobId),
    onSuccess: (r) => { toast.success(`Re-scoring ${r.queued} candidates`); qc.invalidateQueries({ queryKey: ['applications', jobId] }) },
  })
  const remove = useMutation({
    mutationFn: () => api.deleteJob(jobId),
    onSuccess: () => { toast.success('Job deleted'); qc.invalidateQueries({ queryKey: ['jobs'] }); navigate('/app/jobs') },
    onError: (e) => toast.error('Couldn’t delete job', errorMessage(e)),
  })

  if (isLoading) return <PageLoader />
  if (error || !job) return <EmptyState icon={<CircleAlert />} title="Job not found" description={errorMessage(error)} />

  const x = job.extracted
  const closed = job.status === 'closed' || job.status === 'archived'
  const c = job.counts
  const tierTabs: { key: Tier | 'all'; label: string; count: number }[] = [
    { key: 'all', label: 'All', count: c.total },
    { key: 'strong', label: 'Strong match', count: c.strong },
    { key: 'review', label: 'Needs review', count: c.review },
    { key: 'low', label: 'Low fit', count: c.low },
  ]
  const views: { key: View; label: string; icon: React.ReactNode }[] = [
    { key: 'details', label: 'Job details', icon: <FileText /> },
    { key: 'inclusivity', label: 'Inclusivity', icon: <Scale /> },
    { key: 'scoring', label: 'Weights', icon: <SlidersHorizontal /> },
  ]

  return (
    <>
      <div className="mb-3 text-[13px] text-fg-3">
        <Link to="/app/jobs" className="hover:text-fg">Jobs</Link>
        <span className="mx-2">/</span>
        <span className="text-fg-2">{job.title}</span>
      </div>

      <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-[28px] font-semibold tracking-[-0.025em] text-fg">{job.title}</h1>
            <span className={cn('rounded-full px-2.5 py-0.5 text-xs font-semibold', STATUS_STYLE[job.status])}>{titleCase(job.status)}</span>
            <InclusivityBadge report={job.bias_report} />
          </div>
          <p className="mt-1.5 text-[15px] text-fg-2">
            {[job.department, job.location, job.employment_type].filter(Boolean).join(' · ')}
            {(job.department || job.location || job.employment_type) && ' · '}
            {c.total} applicant{c.total === 1 ? '' : 's'} · Posted {timeAgo(job.created_at)}
          </p>
          {x ? (
            <div className="mt-4 flex flex-wrap items-center gap-2">
              <span className="mr-1 text-sm font-medium text-fg">Must-have</span>
              {x.required_skills.slice(0, 8).map((s) => <CriteriaChip key={s} must>{s}</CriteriaChip>)}
              {x.min_years_experience ? <CriteriaChip must>{x.min_years_experience}+ years</CriteriaChip> : null}
              {x.required_skills.length > 8 && <span className="text-xs text-fg-3">+{x.required_skills.length - 8}</span>}
              {x.nice_to_have_skills.length > 0 && <span className="ml-3 mr-1 text-sm font-medium text-fg">Nice to have</span>}
              {x.nice_to_have_skills.slice(0, 6).map((s) => <CriteriaChip key={s}>{s}</CriteriaChip>)}
            </div>
          ) : job.extraction_status === 'pending' ? (
            <p className="mt-4 inline-flex items-center gap-2 text-sm text-brand-text"><Spinner /> AI is drafting must-have and nice-to-have criteria…</p>
          ) : (
            <p className="mt-4 text-sm text-bad-text">Criteria extraction failed. <button className="font-medium underline" onClick={() => api.retryJobExtraction(job.id).then((j) => qc.setQueryData(['job', jobId], j))}>Retry</button></p>
          )}
        </div>
        {can('write') && (
          <div className="flex shrink-0 flex-wrap items-center gap-2">
            <Button variant="secondary" size="lg" onClick={() => setCriteriaOpen(true)} disabled={!x}><SlidersHorizontal /> Edit criteria</Button>
            <Button size="lg" onClick={() => setUploadOpen(true)} disabled={closed}><Upload /> Add resumes</Button>
            <Menu trigger={({ toggle }) => <Button variant="secondary" size="icon" className="size-11" onClick={toggle} aria-label="More actions"><MoreHorizontal /></Button>}>
              {(close) => (
                <>
                  <MenuLabel>Job status</MenuLabel>
                  {(['open', 'paused', 'closed', 'archived'] as const).filter((s) => s !== job.status).map((s) => (
                    <MenuItem key={s} onClick={() => { close(); setStatus.mutate(s) }}>Mark as {s}</MenuItem>
                  ))}
                  <div className="my-1 h-px bg-line" />
                  <MenuItem icon={<RefreshCw />} onClick={() => { close(); rescore.mutate() }}>Re-score all candidates</MenuItem>
                  {can('admin') && <MenuItem icon={<Trash2 />} danger onClick={() => { close(); setConfirmDelete(true) }}>Delete job</MenuItem>}
                </>
              )}
            </Menu>
          </div>
        )}
      </div>

      <div className="-mx-4 mt-6 mb-6 flex flex-col gap-2 border-b border-line px-4 sm:-mx-6 sm:px-6 md:flex-row md:items-end md:justify-between lg:-mx-8 lg:px-8">
        <div role="tablist" className="no-scrollbar flex gap-6 overflow-x-auto">
          {tierTabs.map((t) => {
            const active = view === 'candidates' && tier === t.key
            return (
              <button key={t.key} role="tab" aria-selected={active} onClick={() => { setView('candidates'); setTier(t.key) }}
                      className={cn('-mb-px flex items-center gap-2 whitespace-nowrap border-b-2 pb-3 text-[15px] font-medium transition-colors',
                        active ? 'border-brand text-fg' : 'border-transparent text-fg-2 hover:text-fg')}>
                {t.label}
                <span className="rounded-md bg-surface-3 px-1.5 text-xs text-fg-2 tabular">{t.count}</span>
              </button>
            )
          })}
        </div>
        <div className="no-scrollbar flex gap-1 overflow-x-auto pb-2">
          {views.map((v) => (
            <button key={v.key} onClick={() => setView(v.key)} aria-pressed={view === v.key}
                    className={cn('inline-flex items-center gap-1.5 whitespace-nowrap rounded-lg px-2.5 py-1.5 text-[13px] font-medium transition-colors [&_svg]:size-3.5',
                      view === v.key ? 'bg-brand-soft text-brand-text' : 'text-fg-3 hover:bg-surface-3 hover:text-fg-2')}>
              {v.icon}{v.label}
            </button>
          ))}
        </div>
      </div>

      {view === 'candidates' && <CandidatesTable job={job} tier={tier} onUpload={() => setUploadOpen(true)} />}
      {view === 'details' && (
        <div className="space-y-4">
          <RequirementsTab job={job} />
          <Card>
            <CardHeader title="Job description" />
            <CardBody><pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed text-fg-2">{job.description}</pre></CardBody>
          </Card>
        </div>
      )}
      {view === 'inclusivity' && (
        <Card className="max-w-3xl">
          <CardHeader title="Inclusive language review" description="Deterministic analysis of gender-coded, age-related, ableist and exclusionary wording" />
          <CardBody>{job.bias_report ? <BiasReport report={job.bias_report} /> : <p className="text-sm text-fg-3">Not analyzed yet.</p>}</CardBody>
        </Card>
      )}
      {view === 'scoring' && <ScoringTab key={JSON.stringify(job.scoring_weights)} job={job} />}

      <UploadDialog jobId={job.id} open={uploadOpen} onClose={() => setUploadOpen(false)} />
      {criteriaOpen && <CriteriaDialog job={job} open onClose={() => setCriteriaOpen(false)} />}
      <ConfirmDialog
        open={confirmDelete}
        onClose={() => setConfirmDelete(false)}
        onConfirm={() => remove.mutate()}
        loading={remove.isPending}
        danger
        title="Delete this job?"
        description="This permanently deletes the job, its applications, interviews and evaluations. Candidates stay in your talent pool."
        confirmLabel="Delete job"
      />
    </>
  )
}
