import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Bot, Check, ClipboardCopy, Clock, ExternalLink, Link2, MessageSquare, RefreshCw, Sparkles, XCircle } from 'lucide-react'
import { api } from '@/lib/api'
import type { ApplicationDetail, ChatMessage, InterviewQuestion } from '@/lib/types'
import { dateTime, date, titleCase } from '@/lib/format'
import { cn, errorMessage } from '@/lib/utils'
import { useAuth } from '@/hooks/useAuth'
import { Card, CardBody, CardHeader } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { EmptyState, ProgressBar } from '@/components/ui/misc'
import { ConfirmDialog } from '@/components/ui/dialog'
import { useToast } from '@/components/ui/toast'

const CATEGORY_TONE: Record<InterviewQuestion['category'], 'brand' | 'warn' | 'good' | 'neutral'> = {
  technical: 'brand',
  experience_deep_dive: 'neutral',
  gap_probe: 'warn',
  behavioral: 'good',
  situational: 'neutral',
}

export function Transcript({ messages, candidateName }: { messages: ChatMessage[]; candidateName?: string | null }) {
  return (
    <div className="space-y-3">
      {messages.map((m, i) => {
        const bot = m.role === 'assistant'
        return (
          <div key={i} className={cn('flex gap-2.5', !bot && 'flex-row-reverse')}>
            <div className={cn('flex size-7 shrink-0 items-center justify-center rounded-full text-[11px] font-semibold', bot ? 'bg-brand-soft text-brand-text' : 'bg-surface-3 text-fg-2')}>
              {bot ? <Bot className="size-3.5" /> : (candidateName?.[0] ?? 'C')}
            </div>
            <div className={cn('max-w-[80%] rounded-2xl px-3.5 py-2.5 text-[13px] leading-relaxed', bot ? 'rounded-tl-sm bg-surface-2 text-fg' : 'rounded-tr-sm bg-brand text-brand-fg')}>
              {m.kind === 'follow_up' && <div className="mb-0.5 text-[10px] font-semibold uppercase tracking-wide opacity-70">Follow-up</div>}
              <p className="whitespace-pre-wrap">{m.content}</p>
              <p className={cn('mt-1 text-[10px]', bot ? 'text-fg-3' : 'text-brand-fg/70')}>{dateTime(m.timestamp)}</p>
            </div>
          </div>
        )
      })}
    </div>
  )
}

export function InterviewPanel({ app }: { app: ApplicationDetail }) {
  const qc = useQueryClient()
  const toast = useToast()
  const { can } = useAuth()
  const [link, setLink] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)
  const [confirmCancel, setConfirmCancel] = useState(false)
  const iv = app.interview
  const refresh = () => qc.invalidateQueries({ queryKey: ['application', app.id] })

  const generate = useMutation({
    mutationFn: (replace: boolean) => api.createInterview(app.id, replace),
    onSuccess: (res) => { setLink(res.link); refresh(); toast.success('Interview generated', 'Share the private link with the candidate.') },
    onError: (e) => toast.error('Couldn’t generate interview', errorMessage(e)),
  })
  const relink = useMutation({
    mutationFn: () => api.regenerateLink(app.id),
    onSuccess: (res) => { setLink(res.link); refresh(); toast.success('New link issued', 'The previous link no longer works.') },
    onError: (e) => toast.error('Couldn’t issue link', errorMessage(e)),
  })
  const cancel = useMutation({
    mutationFn: () => api.cancelInterview(app.id),
    onSuccess: () => { setConfirmCancel(false); setLink(null); refresh() },
  })

  async function copy() {
    if (!link) return
    await navigator.clipboard.writeText(link)
    setCopied(true)
    setTimeout(() => setCopied(false), 1800)
  }

  if (!iv) {
    return (
      <Card>
        <EmptyState
          icon={<Sparkles />}
          title="Generate a tailored AI interview"
          description="Claude designs a structured interview for this candidate: deep-dives into their most relevant work, technical checks on core skills, and constructive probes into the gaps screening found."
          action={can('write') && app.status === 'completed' && (
            <Button onClick={() => generate.mutate(false)} loading={generate.isPending}><Sparkles /> Generate interview</Button>
          )}
        />
      </Card>
    )
  }

  const total = iv.plan.questions.length
  const open = iv.status === 'pending' || iv.status === 'in_progress'
  const statusBadge = {
    pending: <Badge tone="neutral" icon={<Clock />}>Not started</Badge>,
    in_progress: <Badge tone="brand" dot>In progress</Badge>,
    completed: <Badge tone="good" icon={<Check />}>Completed</Badge>,
    expired: <Badge tone="warn" icon={<Clock />}>Link expired</Badge>,
    cancelled: <Badge tone="neutral">Cancelled</Badge>,
  }[iv.status]

  return (
    <div className="space-y-4">
      <Card>
        <CardBody className="pt-5">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-[15px] font-semibold text-fg">AI interview</h3>
                {statusBadge}
              </div>
              <p className="mt-1 text-[13px] text-fg-3">
                {iv.answered_questions} of {total} questions answered · ~{iv.plan.estimated_minutes} min · link expires {date(iv.expires_at)}
              </p>
            </div>
            {can('write') && (
              <div className="flex flex-wrap gap-2">
                {iv.status !== 'completed' && (
                  <Button variant="secondary" size="sm" onClick={() => relink.mutate()} loading={relink.isPending}>
                    <Link2 /> {link ? 'New link' : 'Get candidate link'}
                  </Button>
                )}
                {open && <Button variant="ghost" size="sm" onClick={() => setConfirmCancel(true)}><XCircle /> Cancel</Button>}
                {!open && (
                  <Button variant="ghost" size="sm" onClick={() => generate.mutate(true)} loading={generate.isPending}><RefreshCw /> New interview</Button>
                )}
              </div>
            )}
          </div>
          <ProgressBar value={(iv.answered_questions / total) * 100} className="mt-4" />
          {link && (
            <div className="mt-4 rounded-lg border border-[color-mix(in_oklab,var(--brand)_30%,transparent)] bg-brand-soft p-3">
              <div className="mb-1.5 text-xs font-medium text-brand-text">Private candidate link — only shown now, copy it before leaving</div>
              <div className="flex items-center gap-2">
                <code className="min-w-0 flex-1 truncate rounded-md bg-surface px-2.5 py-1.5 font-mono text-xs text-fg">{link}</code>
                <Button size="sm" variant="secondary" onClick={copy}>{copied ? <Check /> : <ClipboardCopy />}{copied ? 'Copied' : 'Copy'}</Button>
                <a href={link} target="_blank" rel="noreferrer" className="inline-flex size-8 items-center justify-center rounded-lg text-fg-2 hover:bg-surface" aria-label="Open link"><ExternalLink className="size-4" /></a>
              </div>
            </div>
          )}
        </CardBody>
      </Card>

      <div className="grid gap-4 xl:grid-cols-2">
        <Card>
          <CardHeader title="Interview plan" description={iv.plan.strategy} />
          <ol className="divide-y divide-line border-t border-line">
            {iv.plan.questions.map((q, i) => {
              const answered = iv.messages.some((m) => m.role === 'candidate' && m.question_id === q.id)
              return (
                <li key={q.id} className="px-5 py-4">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-xs font-semibold text-fg-3">Q{i + 1}</span>
                    <Badge tone={CATEGORY_TONE[q.category]}>{titleCase(q.category)}</Badge>
                    <span className="text-xs font-medium text-fg-2">{q.topic}</span>
                    {answered && <Check className="size-3.5 text-good" aria-label="Answered" />}
                  </div>
                  <p className="mt-1.5 text-sm text-fg">{q.question}</p>
                  <details className="mt-2 text-[13px]">
                    <summary className="cursor-pointer text-xs font-medium text-fg-3 hover:text-fg-2">Rationale & ideal answer signals</summary>
                    <p className="mt-2 text-fg-2">{q.rationale}</p>
                    <ul className="mt-2 space-y-1">
                      {q.ideal_answer_criteria.map((c) => (
                        <li key={c} className="flex gap-2 text-fg-2"><Check className="mt-0.5 size-3.5 shrink-0 text-fg-3" />{c}</li>
                      ))}
                    </ul>
                  </details>
                </li>
              )
            })}
          </ol>
        </Card>
        <Card>
          <CardHeader icon={<MessageSquare />} title="Transcript" description={iv.started_at ? `Started ${dateTime(iv.started_at)}` : 'The candidate hasn’t started yet'} />
          <CardBody className="max-h-[640px] overflow-y-auto">
            {iv.consent_at ? <Transcript messages={iv.messages} candidateName={app.candidate.full_name} /> : (
              <p className="text-sm text-fg-3">The transcript appears once the candidate opens their link and consents.</p>
            )}
          </CardBody>
        </Card>
      </div>

      <ConfirmDialog
        open={confirmCancel}
        onClose={() => setConfirmCancel(false)}
        onConfirm={() => cancel.mutate()}
        loading={cancel.isPending}
        danger
        title="Cancel this interview?"
        description="The candidate’s link will stop working. You can generate a new interview afterwards."
        confirmLabel="Cancel interview"
      />
    </div>
  )
}
