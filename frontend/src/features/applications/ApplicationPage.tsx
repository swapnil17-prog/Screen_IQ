import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Award,
  CalendarClock,
  Check,
  ChevronLeft,
  ChevronRight,
  CircleAlert,
  FileSearch,
  LayoutList,
  MessagesSquare,
  RefreshCw,
  Sparkles,
  Timer,
} from 'lucide-react'
import { api } from '@/lib/api'
import type { ApplicationDetail, Stage } from '@/lib/types'
import { RECOMMENDATIONS, initials, isProcessing, recommendationTone, timeAgo, titleCase } from '@/lib/format'
import { cn, errorMessage } from '@/lib/utils'
import { useAuth, useSession } from '@/hooks/useAuth'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/input'
import { Tabs } from '@/components/ui/tabs'
import { EmptyState, PageLoader, Spinner } from '@/components/ui/misc'
import { ScoreRing } from '@/components/ui/score'
import { Dialog } from '@/components/ui/dialog'
import { useToast } from '@/components/ui/toast'
import { PipelineStepper } from './PipelineStepper'
import { ScoreExplanation } from './panels/OverviewPanel'
import { CriteriaCheck } from './panels/CriteriaCheck'
import { ResumePreview } from './panels/ResumePreview'
import { SkillsPanel } from './panels/SkillsPanel'
import { ExperiencePanel } from './panels/ExperiencePanel'
import { EvidencePanel } from './panels/EvidencePanel'
import { InterviewPanel } from './panels/InterviewPanel'
import { EvaluationPanel } from './panels/EvaluationPanel'

type Tab = 'overview' | 'skills' | 'evidence' | 'experience' | 'interview' | 'evaluation'

function ScoreCard({ app }: { app: ApplicationDetail }) {
  const s = app.screening!
  const ev = app.evaluation
  return (
    <Card className="flex flex-col gap-6 p-6 sm:flex-row sm:items-center">
      <ScoreRing value={s.overall_score} size={132} thickness={11} label="match score" tone="brand" />
      <div className="flex-1 space-y-4">
        {s.components.map((c) => (
          <div key={c.key}>
            <div className="mb-1.5 flex justify-between text-sm">
              <span className="text-fg">{c.label}</span>
              <span className="font-medium text-fg tabular">{Math.round(c.score)}</span>
            </div>
            <div className="h-1.5 overflow-hidden rounded-full bg-track">
              <div className={cn('h-full rounded-full', c.score >= 80 ? 'bg-tier-strong' : c.score >= 60 ? 'bg-tier-review' : 'bg-tier-low')} style={{ width: `${c.score}%` }} />
            </div>
          </div>
        ))}
        {ev?.status === 'completed' && ev.recommendation && (
          <div className="flex items-center gap-2 border-t border-line pt-3 text-sm text-fg-2">
            After AI interview: <span className="font-semibold text-fg tabular">{Math.round(ev.composite_score ?? 0)}</span>
            <Badge tone={recommendationTone(ev.recommendation)}>{RECOMMENDATIONS[ev.recommendation]}</Badge>
          </div>
        )}
      </div>
    </Card>
  )
}

function SummaryCard({ app, onWhy }: { app: ApplicationDetail; onWhy: () => void }) {
  const s = app.screening!
  const ask = [
    ...s.concerns.slice(0, 3),
    ...s.skill_gap.missing_required.slice(0, Math.max(0, 3 - s.concerns.length)).map((m) => `No evidence of ${m} — probe in the interview.`),
  ]
  return (
    <Card className="flex h-full flex-col p-5">
      <h3 className="flex items-center gap-2 text-lg font-semibold tracking-[-0.01em] text-fg"><Sparkles className="size-4 text-brand-text" />AI summary</h3>
      <p className="mt-3 text-[15px] leading-relaxed text-fg">{s.summary}</p>
      {ask.length > 0 && (
        <>
          <div className="mt-5 text-xs font-semibold uppercase tracking-wide text-fg-3">Worth asking in interview</div>
          <ul className="mt-2 space-y-2">
            {ask.map((a) => (
              <li key={a} className="flex gap-2.5 text-sm leading-snug text-fg-2"><span className="mt-[7px] size-1.5 shrink-0 rounded-full bg-tier-low" />{a}</li>
            ))}
          </ul>
        </>
      )}
      <div className="mt-auto pt-5 text-[13px] text-fg-3">
        Generated from resume evidence{s.blind_screening ? ' (identity masked)' : ''} ·{' '}
        <button onClick={onWhy} className="font-medium text-brand-text hover:underline">Why this score?</button>
      </div>
    </Card>
  )
}

function NotesCard({ app }: { app: ApplicationDetail }) {
  const qc = useQueryClient()
  const toast = useToast()
  const { can } = useAuth()
  const [notes, setNotes] = useState(app.notes ?? '')
  const save = useMutation({
    mutationFn: () => api.updateApplication(app.id, { notes }),
    onSuccess: (a) => { qc.setQueryData(['application', app.id], a); toast.success('Note saved') },
    onError: (e) => toast.error('Couldn’t save note', errorMessage(e)),
  })
  return (
    <Card className="p-5">
      <h3 className="text-[15px] font-semibold text-fg">Team notes</h3>
      <Textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={3} placeholder="Add a note for the hiring panel…" disabled={!can('write')} className="mt-3 min-h-20 bg-surface-2" />
      <div className="mt-2 flex items-center justify-between gap-2">
        <span className="text-[13px] text-fg-3">
          {app.stage_changed_by ? `${titleCase(app.stage)} by ${app.stage_changed_by} · ${timeAgo(app.stage_changed_at)}` : `Screened ${timeAgo(app.screened_at ?? app.created_at)}`}
        </span>
        {can('write') && notes !== (app.notes ?? '') && <Button size="sm" onClick={() => save.mutate()} loading={save.isPending}>Save</Button>}
      </div>
    </Card>
  )
}

export function ApplicationPage() {
  const { applicationId = '' } = useParams()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const { can } = useAuth()
  const autoInvite = useSession().organization.settings.auto_invite_on_shortlist
  const [tab, setTab] = useState<Tab>('overview')
  const [whyOpen, setWhyOpen] = useState(false)

  const { data: app, isLoading, error } = useQuery({
    queryKey: ['application', applicationId],
    queryFn: () => api.application(applicationId),
    refetchInterval: (q) => {
      const d = q.state.data
      if (!d) return false
      if (isProcessing(d.status) || d.evaluation?.status === 'running') return 2500
      if (d.interview?.status === 'in_progress' || d.interview?.status === 'pending') return 10_000
      // Just shortlisted: the invitation's interview is being generated in the background
      if (autoInvite && d.stage === 'shortlisted' && !d.interview && d.candidate.email && d.stage_changed_at
          && Date.now() - new Date(d.stage_changed_at).getTime() < 120_000) return 3000
      return false
    },
  })
  // Same list (and cache entry) as the job's ranked table → "Candidate 3 of 48" navigation
  const { data: ranked } = useQuery({
    queryKey: ['applications', app?.job_id, 'all', '', 'score'],
    queryFn: () => api.jobApplications(app!.job_id, { sort: 'score' }),
    enabled: !!app,
  })

  const setStage = useMutation({
    mutationFn: (stage: Stage) => api.updateApplication(applicationId, { stage }),
    onSuccess: (a) => {
      qc.setQueryData(['application', applicationId], a)
      qc.invalidateQueries({ queryKey: ['applications', a.job_id] })
      if (a.stage === 'shortlisted' && autoInvite) {
        if (a.candidate.email) toast.success('Added to shortlist', `An AI interview invitation is being emailed to ${a.candidate.email}.`)
        else toast.success('Added to shortlist', 'No email address on this resume, so no invitation was sent. Generate the interview and share the link yourself.')
        return
      }
      toast.success(a.stage === 'rejected' ? 'Candidate rejected' : a.stage === 'shortlisted' ? 'Added to shortlist' : `Moved to ${titleCase(a.stage)}`)
    },
    onError: (e) => toast.error('Couldn’t update candidate', errorMessage(e)),
  })
  const interview = useMutation({
    mutationFn: () => api.createInterview(applicationId),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['application', applicationId] }); setTab('interview'); toast.success('AI interview generated', 'Copy the private link from the Interview tab.') },
    onError: (e) => toast.error('Couldn’t generate interview', errorMessage(e)),
  })
  const rescreen = useMutation({
    mutationFn: () => api.rescreen(applicationId),
    onSuccess: (a) => qc.setQueryData(['application', applicationId], a),
    onError: (e) => toast.error('Couldn’t re-screen', errorMessage(e)),
  })

  if (isLoading) return <PageLoader />
  if (error || !app) return <EmptyState icon={<CircleAlert />} title="Candidate not found" description={errorMessage(error)} />

  const c = app.candidate
  const s = app.screening
  const processing = isProcessing(app.status)
  const index = ranked?.findIndex((r) => r.id === app.id) ?? -1
  const prev = index > 0 ? ranked![index - 1] : null
  const next = index >= 0 && ranked && index < ranked.length - 1 ? ranked[index + 1] : null
  const meta = [
    c.headline && c.current_company ? `${c.headline} at ${c.current_company}` : c.headline ?? c.current_company,
    c.location,
    app.total_years !== null ? `${Math.round(app.total_years)} year${Math.round(app.total_years) === 1 ? '' : 's'}` : null,
  ].filter(Boolean)

  return (
    <>
      <div className="mb-4 flex items-center justify-between gap-3 text-[13px] text-fg-3">
        <div className="min-w-0 truncate">
          <Link to={`/app/jobs/${app.job_id}`} className="hover:text-fg">{app.job_title ?? 'Job'}</Link>
          <span className="mx-2">/</span>
          <span className="text-fg-2">{c.full_name ?? 'Candidate'}</span>
        </div>
        {index >= 0 && ranked && (
          <div className="flex shrink-0 items-center gap-1">
            <span className="mr-1">Candidate {index + 1} of {ranked.length}</span>
            <Button variant="ghost" size="icon-sm" disabled={!prev} onClick={() => prev && navigate(`/app/applications/${prev.id}`)} aria-label="Previous candidate"><ChevronLeft /></Button>
            <Button variant="ghost" size="icon-sm" disabled={!next} onClick={() => next && navigate(`/app/applications/${next.id}`)} aria-label="Next candidate"><ChevronRight /></Button>
          </div>
        )}
      </div>

      <div className="mb-6 flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex min-w-0 items-center gap-4">
          <span className="flex size-16 shrink-0 items-center justify-center rounded-full bg-brand-soft text-lg font-semibold text-brand-text">{initials(c.full_name)}</span>
          <div className="min-w-0">
            <h1 className="text-[28px] font-semibold tracking-[-0.025em] text-fg">{c.full_name ?? (processing ? 'Processing resume…' : 'Unnamed candidate')}</h1>
            <p className="mt-0.5 text-[15px] text-fg-2">
              {meta.join(' · ') || c.email}
              {' · '}<Link to={`/app/candidates/${c.id}`} className="text-brand-text hover:underline">Profile</Link>
            </p>
          </div>
        </div>
        {can('write') && app.status === 'completed' && (
          <div className="flex shrink-0 flex-wrap items-center gap-2 lg:flex-nowrap">
            {app.stage === 'rejected' ? (
              <Button variant="secondary" size="lg" onClick={() => setStage.mutate('new')} loading={setStage.isPending}>Undo reject</Button>
            ) : (
              <Button variant="secondary" size="lg" className="text-tier-low-text hover:text-tier-low-text" onClick={() => setStage.mutate('rejected')} disabled={setStage.isPending}>Reject</Button>
            )}
            <Button variant="secondary" size="lg" loading={interview.isPending}
                    onClick={() => (app.interview ? setTab('interview') : interview.mutate())}>
              <CalendarClock /> {app.interview ? 'View AI interview' : 'Schedule AI interview'}
            </Button>
            {app.stage === 'shortlisted' ? (
              <Button size="lg" onClick={() => setStage.mutate('new')} title="Remove from shortlist"><Check /> Shortlisted</Button>
            ) : (
              <Button size="lg" onClick={() => setStage.mutate('shortlisted')} disabled={['interviewing', 'offer', 'hired'].includes(app.stage)}>
                <Check /> {['interviewing', 'offer', 'hired'].includes(app.stage) ? titleCase(app.stage) : 'Shortlist'}
              </Button>
            )}
          </div>
        )}
      </div>

      {app.status === 'failed' ? (
        <Card>
          <EmptyState icon={<CircleAlert />} title="Screening failed" description={app.error ?? 'An unexpected error occurred.'}
                      action={can('write') && <Button onClick={() => rescreen.mutate()} loading={rescreen.isPending}><RefreshCw /> Retry screening</Button>} />
        </Card>
      ) : processing || !s ? (
        <>
          <PipelineStepper app={app} className="mb-5" />
          <Card>
            <EmptyState icon={<Spinner className="size-5 text-brand" />} title="Screening in progress"
                        description="Parsing the resume, extracting skills, analyzing experience and matching evidence against the job. Results appear here automatically." />
          </Card>
        </>
      ) : (
        <>
          <Tabs
            className="mb-6"
            value={tab}
            onChange={setTab}
            items={[
              { key: 'overview', label: 'Overview', icon: <LayoutList /> },
              { key: 'skills', label: 'Skill gap', icon: <Sparkles />, count: s.skill_gap.missing_required.length || null },
              { key: 'evidence', label: 'Evidence', icon: <FileSearch />, count: s.requirements.length },
              { key: 'experience', label: 'Experience', icon: <Timer /> },
              { key: 'interview', label: 'AI interview', icon: <MessagesSquare /> },
              { key: 'evaluation', label: 'Evaluation', icon: <Award /> },
            ]}
          />
          {tab === 'overview' && (
            <div className="grid items-start gap-5 xl:grid-cols-[1fr_380px]">
              <div className="space-y-5">
                <ScoreCard app={app} />
                <div className="grid gap-5 lg:grid-cols-2">
                  <SummaryCard app={app} onWhy={() => setWhyOpen(true)} />
                  <CriteriaCheck requirements={s.requirements} />
                </div>
                <PipelineStepper app={app} />
              </div>
              <div className="space-y-5">
                <ResumePreview filename={app.filename} text={app.raw_text} requirements={s.requirements} />
                <NotesCard key={app.notes ?? ''} app={app} />
              </div>
            </div>
          )}
          {tab === 'skills' && <SkillsPanel gap={s.skill_gap} />}
          {tab === 'evidence' && <EvidencePanel requirements={s.requirements} />}
          {tab === 'experience' && <ExperiencePanel exp={app.experience} fit={s.experience_fit} />}
          {tab === 'interview' && <InterviewPanel app={app} />}
          {tab === 'evaluation' && <EvaluationPanel app={app} />}
          <Dialog open={whyOpen} onClose={() => setWhyOpen(false)} size="xl" title="Why this score?"
                  description="The match score is the weighted sum of four components; each lists the evidence-based reasons behind it.">
            <ScoreExplanation s={s} />
          </Dialog>
        </>
      )}
    </>
  )
}
