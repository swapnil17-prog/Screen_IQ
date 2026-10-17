import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CircleAlert, Search, UploadCloud, Users } from 'lucide-react'
import { api } from '@/lib/api'
import type { ApplicationSummary, JobDetail, Stage, Tier } from '@/lib/types'
import { STAGES, isProcessing, pipelineLabel, years } from '@/lib/format'
import { cn, errorMessage } from '@/lib/utils'
import { useAuth, useSession } from '@/hooks/useAuth'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input, Select } from '@/components/ui/input'
import { Avatar, EmptyState, PageLoader, Spinner } from '@/components/ui/misc'
import { useToast } from '@/components/ui/toast'
import { ScoreBar, SkillChip, StatusPill } from '@/components/ui/tier'

const PAGE = 25
const CHIPS = 3

/** Criteria in order (as in the job header), but never hide that a must-have is missing. */
function pickChips(chips: ApplicationSummary['skill_chips']) {
  const shown = chips.slice(0, CHIPS)
  const hiddenMissing = chips.slice(CHIPS).filter((c) => c.importance === 'required' && c.status === 'missing')
  if (hiddenMissing.length && !shown.some((c) => c.status === 'missing')) shown[shown.length - 1] = hiddenMissing.shift()!
  return { shown, moreMissing: hiddenMissing.length }
}

const EXPERIENCE = [
  { key: 'any', label: 'Experience: Any', test: () => true },
  { key: 'lt3', label: 'Under 3 years', test: (y: number | null) => y !== null && y < 3 },
  { key: '3to5', label: '3–5 years', test: (y: number | null) => y !== null && y >= 3 && y <= 5 },
  { key: '5plus', label: '5+ years', test: (y: number | null) => y !== null && y >= 5 },
  { key: '8plus', label: '8+ years', test: (y: number | null) => y !== null && y >= 8 },
] as const

type SortKey = 'score' | 'final' | 'recent' | 'name'

function Row({ a, selected, onSelect }: { a: ApplicationSummary; selected: boolean; onSelect: (v: boolean) => void }) {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const processing = isProcessing(a.status)
  const retry = useMutation({
    mutationFn: () => api.rescreen(a.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['applications', a.job_id] }),
  })
  const subtitle = [a.candidate.headline, a.candidate.current_company].filter(Boolean).join(' · ')
  const { shown, moreMissing } = pickChips(a.skill_chips)

  return (
    <tr onClick={() => navigate(`/app/applications/${a.id}`)} className={cn('group cursor-pointer border-t border-line transition-colors hover:bg-surface-2', selected && 'bg-brand-soft/40')}>
      <td className="w-12 py-4 pl-5 pr-2" onClick={(e) => e.stopPropagation()}>
        <input type="checkbox" checked={selected} onChange={(e) => onSelect(e.target.checked)} aria-label={`Select ${a.candidate.full_name ?? 'candidate'}`} className="size-4 accent-[var(--brand)]" />
      </td>
      <td className="py-4 pr-4">
        <div className="flex items-center gap-3">
          <Avatar name={a.candidate.full_name} className="bg-surface-3 text-fg-2" />
          <div className="min-w-0">
            <div className="truncate text-[15px] font-semibold text-fg group-hover:text-brand-text">
              {a.candidate.full_name ?? (processing ? 'Parsing resume…' : 'Unnamed candidate')}
            </div>
            <div className="truncate text-[13px] text-fg-3">{subtitle || a.candidate.email || '—'}</div>
          </div>
        </div>
      </td>
      <td className="py-4 pr-4">
        {processing ? (
          <span className="inline-flex items-center gap-2 text-xs text-brand-text"><Spinner className="size-3.5" />{pipelineLabel(a.status)}</span>
        ) : a.status === 'failed' ? (
          <span className="inline-flex items-center gap-2 text-xs text-bad-text" title={a.error ?? undefined}>
            <CircleAlert className="size-3.5" /> Failed
            <button onClick={(e) => { e.stopPropagation(); retry.mutate() }} className="rounded px-1.5 py-0.5 font-medium text-brand-text hover:bg-brand-soft">Retry</button>
          </span>
        ) : (
          <ScoreBar value={a.screening_score} />
        )}
      </td>
      <td className="hidden py-4 pr-4 lg:table-cell">
        <div className="flex max-w-60 flex-wrap gap-1">
          {shown.map((c) => <SkillChip key={c.skill} skill={c.skill} status={c.status} />)}
          {moreMissing > 0 && <span className="self-center text-xs text-tier-low-text" title="More must-haves missing">+{moreMissing} missing</span>}
        </div>
      </td>
      <td className="hidden whitespace-nowrap py-4 pr-4 text-sm text-fg-2 tabular md:table-cell">{years(a.total_years)}</td>
      <td className="hidden py-4 pr-4 xl:table-cell">
        <p className="line-clamp-2 max-w-56 text-[13px] leading-snug text-fg-2">{a.one_liner ?? '—'}</p>
      </td>
      <td className="py-4 pr-5">
        <StatusPill stage={a.stage} tier={a.tier} />
      </td>
    </tr>
  )
}

export function CandidatesTable({ job, tier, onUpload }: { job: JobDetail; tier: Tier | 'all'; onUpload: () => void }) {
  const { can } = useAuth()
  const autoInvite = useSession().organization.settings.auto_invite_on_shortlist
  const qc = useQueryClient()
  const toast = useToast()
  const [q, setQ] = useState('')
  const [exp, setExp] = useState<(typeof EXPERIENCE)[number]['key']>('any')
  const [stage, setStage] = useState('')
  const [sort, setSort] = useState<SortKey>('score')
  const [page, setPage] = useState(0)
  const [selected, setSelected] = useState<Set<string>>(new Set())

  const { data, isLoading } = useQuery({
    queryKey: ['applications', job.id, tier, stage, sort],
    queryFn: () => api.jobApplications(job.id, { tier: tier === 'all' ? undefined : tier, stage: stage || undefined, sort }),
    refetchInterval: (query) => (query.state.data?.some((a) => isProcessing(a.status)) ? 2500 : false),
  })

  const rows = useMemo(() => {
    const needle = q.trim().toLowerCase()
    const test = EXPERIENCE.find((e) => e.key === exp)!.test
    return (data ?? []).filter((a) => {
      if (!test(a.total_years)) return false
      if (!needle) return true
      const hay = [a.candidate.full_name, a.candidate.headline, a.candidate.current_company, ...a.skill_chips.map((c) => c.skill)]
        .filter(Boolean).join(' ').toLowerCase()
      return hay.includes(needle)
    })
  }, [data, q, exp])

  const pageRows = rows.slice(page * PAGE, page * PAGE + PAGE)
  const allOnPage = pageRows.length > 0 && pageRows.every((r) => selected.has(r.id))

  const bulk = useMutation({
    mutationFn: async (to: Stage) => {
      const ids = [...selected]
      await Promise.all(ids.map((id) => api.updateApplication(id, { stage: to })))
      return { to, count: ids.length }
    },
    onSuccess: ({ to, count }) => {
      toast.success(`${count} candidate${count > 1 ? 's' : ''} ${to === 'rejected' ? 'rejected' : `moved to ${to}`}`,
        to === 'shortlisted' && autoInvite ? 'AI interview invitations are being emailed to them.' : undefined)
      setSelected(new Set())
      qc.invalidateQueries({ queryKey: ['applications', job.id] })
      qc.invalidateQueries({ queryKey: ['job', job.id] })
    },
    onError: (e) => toast.error('Bulk update failed', errorMessage(e)),
  })

  function toggle(id: string, on: boolean) {
    setSelected((cur) => {
      const next = new Set(cur)
      if (on) next.add(id)
      else next.delete(id)
      return next
    })
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
        <div className="relative lg:w-80">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-fg-3" />
          <Input value={q} onChange={(e) => { setQ(e.target.value); setPage(0) }} placeholder="Filter by name or skill" className="h-10 pl-9" aria-label="Filter by name or skill" />
        </div>
        <Select value={exp} onChange={(e) => { setExp(e.target.value as typeof exp); setPage(0) }} aria-label="Experience" className="h-10 w-44">
          {EXPERIENCE.map((e) => <option key={e.key} value={e.key}>{e.label}</option>)}
        </Select>
        <Select value={stage} onChange={(e) => { setStage(e.target.value); setPage(0) }} aria-label="Stage" className="h-10 w-40">
          <option value="">Stage: Any</option>
          {STAGES.map((s) => <option key={s.key} value={s.key}>{s.label}</option>)}
        </Select>
        <div className="flex items-center gap-2 lg:ml-auto">
          <span className="text-sm text-fg-3">Sort by</span>
          <Select value={sort} onChange={(e) => setSort(e.target.value as SortKey)} aria-label="Sort by" className="h-10 w-44 font-medium">
            <option value="score">Match score ↓</option>
            <option value="final">Final score ↓</option>
            <option value="recent">Newest</option>
            <option value="name">Name</option>
          </Select>
        </div>
      </div>

      {selected.size > 0 && can('write') && (
        <div className="flex animate-slide-up items-center gap-3 rounded-xl bg-ink px-4 py-2.5 text-sm text-ink-fg">
          <span className="font-medium">{selected.size} selected</span>
          <div className="ml-auto flex gap-2">
            <Button size="sm" onClick={() => bulk.mutate('shortlisted')} loading={bulk.isPending}>Shortlist</Button>
            <Button size="sm" variant="secondary" onClick={() => bulk.mutate('rejected')} disabled={bulk.isPending}>Reject</Button>
            <Button size="sm" variant="ghost" className="text-ink-fg/80 hover:bg-white/10 hover:text-ink-fg" onClick={() => setSelected(new Set())}>Clear</Button>
          </div>
        </div>
      )}

      <Card className="overflow-hidden">
        {isLoading ? <PageLoader /> : rows.length === 0 ? (
          <EmptyState
            icon={<Users />}
            title={data?.length ? 'No candidates match these filters' : tier === 'all' ? 'No candidates yet' : 'No candidates in this group'}
            description={data?.length ? 'Try clearing a filter.' : 'Add resumes and ScreenIQ ranks them with evidence for every score.'}
            action={!data?.length && tier === 'all' && can('write') && <Button onClick={onUpload}><UploadCloud /> Add resumes</Button>}
          />
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-left">
                <thead>
                  <tr className="bg-surface-2 text-[13px] text-fg-3">
                    <th className="w-12 py-3.5 pl-5 pr-2 font-medium">
                      <input type="checkbox" checked={allOnPage} aria-label="Select all on this page" className="size-4 accent-[var(--brand)]"
                             onChange={(e) => setSelected((cur) => {
                               const next = new Set(cur)
                               pageRows.forEach((r) => (e.target.checked ? next.add(r.id) : next.delete(r.id)))
                               return next
                             })} />
                    </th>
                    <th className="py-3.5 pr-4 font-medium">Candidate</th>
                    <th className="py-3.5 pr-4 font-medium">Match score</th>
                    <th className="hidden py-3.5 pr-4 font-medium lg:table-cell">Skills vs. criteria</th>
                    <th className="hidden py-3.5 pr-4 font-medium md:table-cell">Exp.</th>
                    <th className="hidden py-3.5 pr-4 font-medium xl:table-cell">AI summary</th>
                    <th className="py-3.5 pr-5 font-medium">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {pageRows.map((a) => <Row key={a.id} a={a} selected={selected.has(a.id)} onSelect={(v) => toggle(a.id, v)} />)}
                </tbody>
              </table>
            </div>
            <div className="flex items-center justify-between border-t border-line px-5 py-4 text-sm text-fg-2">
              <span>Showing {page * PAGE + 1}–{Math.min((page + 1) * PAGE, rows.length)} of {rows.length}</span>
              <div className="flex gap-2">
                <Button variant="secondary" size="sm" disabled={page === 0} onClick={() => setPage(page - 1)}>Previous</Button>
                <Button variant="secondary" size="sm" disabled={(page + 1) * PAGE >= rows.length} onClick={() => setPage(page + 1)}>Next</Button>
              </div>
            </div>
          </>
        )}
      </Card>
    </div>
  )
}
