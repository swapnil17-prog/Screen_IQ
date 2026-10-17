import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ChevronLeft, CircleAlert, Mail, MapPin, Phone, Plus, RefreshCw, Trash2 } from 'lucide-react'
import { api } from '@/lib/api'
import { isProcessing, titleCase, years } from '@/lib/format'
import { errorMessage } from '@/lib/utils'
import { useAuth } from '@/hooks/useAuth'
import { Card, CardHeader } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Select } from '@/components/ui/input'
import { Avatar, EmptyState, PageLoader, Spinner } from '@/components/ui/misc'
import { ConfirmDialog, Dialog } from '@/components/ui/dialog'
import { ScorePill } from '@/components/ui/score'
import { useToast } from '@/components/ui/toast'
import { ResumePanel } from '../applications/panels/ResumePanel'

export function CandidatePage() {
  const { candidateId = '' } = useParams()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const { can } = useAuth()
  const [applyOpen, setApplyOpen] = useState(false)
  const [jobId, setJobId] = useState('')
  const [confirmErase, setConfirmErase] = useState(false)

  const { data: c, isLoading, error } = useQuery({
    queryKey: ['candidate', candidateId],
    queryFn: () => api.candidate(candidateId),
    refetchInterval: (q) => (q.state.data?.status === 'processing' || q.state.data?.applications.some((a) => isProcessing(a.status)) ? 3000 : false),
  })
  const { data: jobs } = useQuery({ queryKey: ['jobs', 'open'], queryFn: () => api.jobs({ status: 'open' }), enabled: applyOpen })

  const apply = useMutation({
    mutationFn: () => api.applyCandidate(candidateId, jobId),
    onSuccess: (a) => { setApplyOpen(false); toast.success(`Screening against ${a.job_title}`); qc.invalidateQueries({ queryKey: ['candidate', candidateId] }) },
    onError: (e) => toast.error('Couldn’t add to job', errorMessage(e)),
  })
  const reprocess = useMutation({
    mutationFn: () => api.reprocessCandidate(candidateId),
    onSuccess: () => { toast.info('Re-processing resume'); qc.invalidateQueries({ queryKey: ['candidate', candidateId] }) },
  })
  const erase = useMutation({
    mutationFn: () => api.deleteCandidate(candidateId),
    onSuccess: () => { toast.success('Candidate data erased'); qc.invalidateQueries({ queryKey: ['candidates'] }); navigate('/app/candidates') },
    onError: (e) => toast.error('Couldn’t erase candidate', errorMessage(e)),
  })

  if (isLoading) return <PageLoader />
  if (error || !c) return <EmptyState icon={<CircleAlert />} title="Candidate not found" description={errorMessage(error)} />

  const appliedIds = new Set(c.applications.map((a) => a.job_id))
  const available = (jobs ?? []).filter((j) => !appliedIds.has(j.id))

  return (
    <>
      <div className="mb-3 text-[13px] text-fg-3">
        <Link to="/app/candidates" className="inline-flex items-center gap-1 hover:text-fg"><ChevronLeft className="size-4" />Talent pool</Link>
      </div>
      <div className="mb-6 flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex items-center gap-4">
          <Avatar name={c.full_name} size="lg" />
          <div>
            <h1 className="text-2xl font-semibold tracking-[-0.02em] text-fg">{c.full_name ?? 'Unnamed candidate'}</h1>
            <div className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-[13px] text-fg-2">
              {c.headline && <span>{c.headline}</span>}
              {c.email && <span className="inline-flex items-center gap-1.5"><Mail className="size-3.5 text-fg-3" />{c.email}</span>}
              {c.phone && <span className="inline-flex items-center gap-1.5"><Phone className="size-3.5 text-fg-3" />{c.phone}</span>}
              {c.location && <span className="inline-flex items-center gap-1.5"><MapPin className="size-3.5 text-fg-3" />{c.location}</span>}
              <span>{years(c.total_years)} experience</span>
            </div>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          {can('write') && <Button onClick={() => setApplyOpen(true)}><Plus /> Screen for another job</Button>}
          {can('write') && <Button variant="secondary" size="icon" title="Re-process resume" aria-label="Re-process resume" onClick={() => reprocess.mutate()}><RefreshCw /></Button>}
          {can('admin') && <Button variant="secondary" size="icon" title="Erase candidate data" aria-label="Erase candidate data" onClick={() => setConfirmErase(true)}><Trash2 /></Button>}
        </div>
      </div>

      {c.status === 'failed' && (
        <div className="mb-4 flex items-center gap-2 rounded-lg bg-bad-soft px-4 py-3 text-sm text-bad-text"><CircleAlert className="size-4" />{c.error}</div>
      )}
      {c.status === 'processing' && (
        <div className="mb-4 flex items-center gap-2 rounded-lg bg-brand-soft px-4 py-3 text-sm text-brand-text"><Spinner />Parsing and analyzing the resume…</div>
      )}

      <div className="grid items-start gap-5 xl:grid-cols-[1fr_340px]">
        <ResumePanel profile={c.extracted} skills={c.extracted?.skills ?? c.skills} rawText={c.raw_text} />
        <Card>
          <CardHeader title="Applications" description={`${c.applications.length} job${c.applications.length === 1 ? '' : 's'}`} />
          <ul className="divide-y divide-line border-t border-line">
            {c.applications.map((a) => (
              <li key={a.id}>
                <Link to={`/app/applications/${a.id}`} className="flex items-center gap-3 px-5 py-3 hover:bg-surface-2">
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm font-medium text-fg">{a.job_title}</div>
                    <div className="mt-0.5 flex items-center gap-1.5">
                      <Badge>{titleCase(a.stage)}</Badge>
                      {isProcessing(a.status) && <Spinner className="size-3 text-brand" />}
                    </div>
                  </div>
                  <ScorePill value={a.final_score ?? a.screening_score} />
                </Link>
              </li>
            ))}
          </ul>
          <div className="px-5 py-3 text-xs text-fg-3">File: {c.filename}</div>
        </Card>
      </div>

      <Dialog
        open={applyOpen}
        onClose={() => setApplyOpen(false)}
        title="Screen for another job"
        description="Reuses the parsed resume and embeddings — only matching and scoring run again."
        footer={<><Button variant="secondary" onClick={() => setApplyOpen(false)}>Cancel</Button><Button disabled={!jobId} loading={apply.isPending} onClick={() => apply.mutate()}>Start screening</Button></>}
      >
        {available.length === 0 ? <p className="text-sm text-fg-3">No other open jobs available.</p> : (
          <Select value={jobId} onChange={(e) => setJobId(e.target.value)} aria-label="Job">
            <option value="">Select a job…</option>
            {available.map((j) => <option key={j.id} value={j.id}>{j.title}</option>)}
          </Select>
        )}
      </Dialog>
      <ConfirmDialog
        open={confirmErase}
        onClose={() => setConfirmErase(false)}
        onConfirm={() => erase.mutate()}
        loading={erase.isPending}
        danger
        title="Erase this candidate?"
        description="Right to erasure: permanently deletes the resume, vectors, applications, interviews and evaluations. An anonymized audit entry is kept."
        confirmLabel="Erase permanently"
      />
    </>
  )
}
