import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { CircleAlert, ListChecks, RefreshCw } from 'lucide-react'
import { api } from '@/lib/api'
import type { JobDetail, ScoringWeights } from '@/lib/types'
import { titleCase } from '@/lib/format'
import { errorMessage } from '@/lib/utils'
import { useAuth } from '@/hooks/useAuth'
import { Card, CardBody, CardHeader } from '@/components/ui/card'
import { Chip } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { EmptyState, Spinner } from '@/components/ui/misc'
import { useToast } from '@/components/ui/toast'
import { WeightsEditor } from './WeightsEditor'

export function RequirementsTab({ job }: { job: JobDetail }) {
  const qc = useQueryClient()
  const retry = useMutation({
    mutationFn: () => api.retryJobExtraction(job.id),
    onSuccess: (j) => qc.setQueryData(['job', job.id], j),
  })
  if (job.extraction_status === 'pending') {
    return <Card><EmptyState icon={<Spinner className="size-5" />} title="Extracting requirements…" description="The AI is reading the job description. This usually takes a few seconds." /></Card>
  }
  if (!job.extracted) {
    return (
      <Card>
        <EmptyState
          icon={<CircleAlert />}
          title="Requirement extraction failed"
          description={job.extraction_error ?? 'Please retry.'}
          action={<Button onClick={() => retry.mutate()} loading={retry.isPending}><RefreshCw /> Retry</Button>}
        />
      </Card>
    )
  }
  const x = job.extracted
  return (
    <div className="grid gap-4 lg:grid-cols-3">
      <Card className="lg:col-span-2">
        <CardHeader title="Skills" description="Candidates are matched on these using exact, alias and semantic (embedding) matching" />
        <CardBody className="space-y-4">
          <div>
            <div className="mb-2 text-xs font-medium text-fg-2">Required · {x.required_skills.length}</div>
            <div className="flex flex-wrap gap-1.5">{x.required_skills.map((s) => <Chip key={s}>{s}</Chip>)}</div>
          </div>
          <div>
            <div className="mb-2 text-xs font-medium text-fg-2">Nice to have · {x.nice_to_have_skills.length}</div>
            <div className="flex flex-wrap gap-1.5">
              {x.nice_to_have_skills.length ? x.nice_to_have_skills.map((s) => <Chip key={s} muted>{s}</Chip>) : <span className="text-xs text-fg-3">None listed</span>}
            </div>
          </div>
        </CardBody>
        <CardHeader title="Responsibilities" className="border-t border-line pt-4" />
        <CardBody>
          <ul className="space-y-2">
            {x.responsibilities.map((r) => (
              <li key={r} className="flex gap-2 text-sm text-fg-2"><ListChecks className="mt-0.5 size-4 shrink-0 text-fg-3" />{r}</li>
            ))}
          </ul>
        </CardBody>
      </Card>
      <Card>
        <CardHeader title="Role profile" />
        <CardBody>
          <dl className="space-y-3 text-sm">
            {[
              ['Role', x.role_title],
              ['Seniority', x.seniority ? titleCase(x.seniority) : 'Not specified'],
              ['Minimum experience', x.min_years_experience ? `${x.min_years_experience}+ years` : 'Not specified'],
              ['Education', x.education_requirement ?? 'Not specified'],
              ['Domain', x.domain ?? '—'],
            ].map(([k, v]) => (
              <div key={k}>
                <dt className="text-xs text-fg-3">{k}</dt>
                <dd className="mt-0.5 text-fg">{v}</dd>
              </div>
            ))}
          </dl>
        </CardBody>
      </Card>
    </div>
  )
}

export function ScoringTab({ job }: { job: JobDetail }) {
  const { can } = useAuth()
  const qc = useQueryClient()
  const toast = useToast()
  const [weights, setWeights] = useState<ScoringWeights>(job.scoring_weights)
  const dirty = JSON.stringify(weights) !== JSON.stringify(job.scoring_weights)

  const save = useMutation({
    mutationFn: async (reset: boolean) => {
      const j = await api.updateJob(job.id, reset ? { clear_scoring_weights: true } : { scoring_weights: weights })
      await api.rescoreJob(job.id)
      return j
    },
    onSuccess: (j) => {
      qc.setQueryData(['job', job.id], j)
      qc.invalidateQueries({ queryKey: ['applications', job.id] })
      toast.success('Weights saved', 'All candidates are being re-scored.')
    },
    onError: (e) => toast.error('Couldn’t save weights', errorMessage(e)),
  })

  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_320px]">
      <Card>
        <CardHeader
          title="Screening score weights"
          description={job.has_custom_weights ? 'Custom weights for this job' : 'Using your organization’s default weights'}
        />
        <CardBody>
          <WeightsEditor value={weights} onChange={setWeights} disabled={!can('write')} />
          {can('write') && (
            <div className="mt-6 flex flex-wrap gap-2 border-t border-line pt-4">
              <Button onClick={() => save.mutate(false)} disabled={!dirty} loading={save.isPending && dirty}>Save & re-score</Button>
              {job.has_custom_weights && (
                <Button variant="secondary" onClick={() => save.mutate(true)} loading={save.isPending && !dirty}>Reset to organization default</Button>
              )}
            </div>
          )}
        </CardBody>
      </Card>
      <Card className="h-fit">
        <CardHeader title="How scoring works" />
        <CardBody className="space-y-3 text-[13px] text-fg-2">
          <p>Each candidate gets four component scores (0–100). The screening score is their weighted sum, and every component lists the reasons behind it.</p>
          <p>Employment gaps are displayed for context but <strong className="text-fg">never</strong> affect scores.</p>
          <p>After an AI interview, the final score blends screening and interview performance using your organization’s final weights.</p>
        </CardBody>
      </Card>
    </div>
  )
}

