import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Award, CheckCircle2, CircleAlert, FileJson, Quote, RefreshCw, Scale, ShieldAlert, ShieldCheck, XCircle } from 'lucide-react'
import { api } from '@/lib/api'
import type { ApplicationDetail, Evaluation } from '@/lib/types'
import { RECOMMENDATIONS, dateTime, recommendationTone, titleCase } from '@/lib/format'
import { cn, errorMessage } from '@/lib/utils'
import { useAuth } from '@/hooks/useAuth'
import { Card, CardBody, CardHeader } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { EmptyState, ProgressBar, Spinner } from '@/components/ui/misc'
import { ScoreRing } from '@/components/ui/score'
import { seriesColor } from '@/components/charts/charts'
import { useToast } from '@/components/ui/toast'

function BiasAuditCard({ ev }: { ev: Evaluation }) {
  const b = ev.bias_audit
  if (!b) return null
  const tone = b.risk === 'low' ? 'good' : b.risk === 'medium' ? 'warn' : 'bad'
  const Icon = b.risk === 'low' ? ShieldCheck : ShieldAlert
  const masked = Object.entries(b.entities_masked)
  return (
    <Card>
      <CardHeader
        icon={<Scale />}
        title="Counterfactual bias audit"
        description="The transcript was graded twice — with identity visible and with identity masked — to detect sensitivity to demographic proxies"
        action={<Badge tone={tone} icon={<Icon />}>{titleCase(b.risk)} risk</Badge>}
      />
      <CardBody className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-3">
          {[
            { label: 'Identity visible', value: b.unmasked_score, color: seriesColor(0) },
            { label: 'Identity masked', value: b.masked_score, color: seriesColor(1) },
          ].map((x) => (
            <div key={x.label} className="rounded-lg border border-line bg-surface-2 p-3">
              <div className="flex items-center gap-1.5 text-xs text-fg-3"><span className="size-2 rounded-[2px]" style={{ background: x.color }} />{x.label}</div>
              <div className="mt-1 text-xl font-semibold text-fg tabular">{Math.round(x.value)}</div>
              <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-track"><div className="h-full rounded-full" style={{ width: `${x.value}%`, background: x.color }} /></div>
            </div>
          ))}
          <div className="rounded-lg border border-line bg-surface-2 p-3">
            <div className="text-xs text-fg-3">Delta (threshold ±{b.threshold})</div>
            <div className="mt-1 text-xl font-semibold text-fg tabular">{b.delta > 0 ? '+' : ''}{b.delta.toFixed(1)}</div>
            <div className="mt-1 text-xs text-fg-3">{b.flagged ? 'Exceeds threshold' : 'Within tolerance'}</div>
          </div>
        </div>
        <p className="text-[13px] text-fg-2">{b.explanation}</p>
        {b.per_question.some((q) => q.delta !== 0) && (
          <div className="flex flex-wrap gap-2 text-xs">
            {b.per_question.map((q) => (
              <span key={q.question_id} className="rounded-md bg-surface-3 px-2 py-1 text-fg-2 tabular">{q.question_id.toUpperCase()}: {q.delta > 0 ? '+' : ''}{q.delta}</span>
            ))}
          </div>
        )}
        <div className="flex flex-wrap items-center gap-1.5 text-xs text-fg-3">
          <span>Masked in answers:</span>
          {masked.length ? masked.map(([k, v]) => <Badge key={k}>{titleCase(k)} ×{v}</Badge>) : <span>no identity signals found in the answers</span>}
        </div>
        <ul className="space-y-1 border-t border-line pt-3 text-xs text-fg-3">
          {b.notes.map((n) => <li key={n}>• {n}</li>)}
        </ul>
      </CardBody>
    </Card>
  )
}

export function EvaluationPanel({ app }: { app: ApplicationDetail }) {
  const qc = useQueryClient()
  const toast = useToast()
  const { can } = useAuth()
  const ev = app.evaluation
  const hasAnswers = app.interview?.messages.some((m) => m.role === 'candidate')

  const run = useMutation({
    mutationFn: () => api.runEvaluation(app.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['application', app.id] }),
    onError: (e) => toast.error('Couldn’t start evaluation', errorMessage(e)),
  })

  if (!ev) {
    return (
      <Card>
        <EmptyState
          icon={<Award />}
          title="No evaluation yet"
          description={hasAnswers ? 'Run the LLM-as-a-judge evaluation on the interview answers so far.' : 'The final evaluation runs automatically when the candidate completes the AI interview.'}
          action={can('write') && hasAnswers && <Button onClick={() => run.mutate()} loading={run.isPending}><Award /> Evaluate now</Button>}
        />
      </Card>
    )
  }
  if (ev.status === 'running') {
    return <Card><EmptyState icon={<Spinner className="size-5 text-brand" />} title="Evaluating the interview…" description="Grading each answer against its rubric and running the counterfactual bias audit. This takes up to a minute." /></Card>
  }
  if (ev.status === 'failed') {
    return (
      <Card>
        <EmptyState
          icon={<CircleAlert />}
          title="Evaluation failed"
          description={ev.error ?? 'Please retry.'}
          action={can('write') && <Button onClick={() => run.mutate()} loading={run.isPending}><RefreshCw /> Retry</Button>}
        />
      </Card>
    )
  }

  const rubric = ev.rubric!
  const questions = app.interview?.plan.questions ?? []
  return (
    <div className="space-y-4">
      <Card>
        <CardBody className="flex flex-col gap-6 pt-5 md:flex-row md:items-center">
          <ScoreRing value={ev.composite_score} size={112} label="final" />
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              {ev.recommendation && <Badge tone={recommendationTone(ev.recommendation)} className="text-sm">{RECOMMENDATIONS[ev.recommendation]}</Badge>}
              <span className="text-xs text-fg-3">Evaluated {dateTime(ev.updated_at)}</span>
            </div>
            <p className="mt-2 text-sm leading-relaxed text-fg">{rubric.summary}</p>
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              {ev.components.map((c) => (
                <div key={c.key}>
                  <div className="mb-1 flex justify-between text-[13px]">
                    <span className="text-fg-2">{c.label} <span className="text-fg-3">({Math.round(c.weight * 100)}%)</span></span>
                    <span className="font-semibold text-fg tabular">{Math.round(c.score)}</span>
                  </div>
                  <ProgressBar value={c.score} tone="seq" />
                </div>
              ))}
            </div>
          </div>
          {can('write') && (
            <Button variant="ghost" size="sm" onClick={() => run.mutate()} loading={run.isPending} className="self-start"><RefreshCw /> Re-run</Button>
          )}
        </CardBody>
      </Card>

      {(rubric.key_strengths.length > 0 || rubric.key_risks.length > 0) && (
        <div className="grid gap-4 md:grid-cols-2">
          <Card><CardHeader title="Key strengths" /><CardBody><ul className="space-y-1.5">{rubric.key_strengths.length ? rubric.key_strengths.map((s) => <li key={s} className="flex gap-2 text-sm text-fg-2"><CheckCircle2 className="mt-0.5 size-4 shrink-0 text-good" />{s}</li>) : <li className="text-sm text-fg-3">None noted</li>}</ul></CardBody></Card>
          <Card><CardHeader title="Key risks" /><CardBody><ul className="space-y-1.5">{rubric.key_risks.length ? rubric.key_risks.map((s) => <li key={s} className="flex gap-2 text-sm text-fg-2"><XCircle className="mt-0.5 size-4 shrink-0 text-bad" />{s}</li>) : <li className="text-sm text-fg-3">None noted</li>}</ul></CardBody></Card>
        </div>
      )}

      <Card>
        <CardHeader title="Rubric by question" description="LLM-as-a-judge: every ideal-answer criterion checked, with verbatim evidence from the candidate’s answers" />
        <div className="divide-y divide-line border-t border-line">
          {rubric.question_scores.map((q, i) => {
            const plan = questions.find((x) => x.id === q.question_id)
            return (
              <div key={q.question_id} className="space-y-3 px-5 py-4">
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <div className="text-xs font-semibold text-fg-3">Q{i + 1}{plan ? ` · ${titleCase(plan.category)} · ${plan.topic}` : ''}</div>
                    {plan && <p className="mt-1 text-sm text-fg">{plan.question}</p>}
                  </div>
                  <span className="shrink-0 text-lg font-semibold text-fg tabular">{q.score}<span className="text-xs font-normal text-fg-3">/100</span></span>
                </div>
                <div className="grid gap-3 sm:grid-cols-3">
                  {[['Technical depth', q.technical_depth], ['Communication', q.communication], ['Problem solving', q.problem_solving]].map(([k, v]) => (
                    <div key={k as string}>
                      <div className="mb-1 flex justify-between text-xs"><span className="text-fg-3">{k}</span><span className="font-medium text-fg tabular">{v}/10</span></div>
                      <ProgressBar value={(v as number) * 10} tone="seq" />
                    </div>
                  ))}
                </div>
                <ul className="space-y-1.5">
                  {q.criteria.map((c) => (
                    <li key={c.criterion} className="text-[13px]">
                      <div className="flex items-start gap-2">
                        {c.met ? <CheckCircle2 className="mt-0.5 size-3.5 shrink-0 text-good" /> : <XCircle className="mt-0.5 size-3.5 shrink-0 text-bad" />}
                        <span className={cn('flex-1', c.met ? 'text-fg' : 'text-fg-2')}>{c.criterion}</span>
                        <span className="text-xs text-fg-3 tabular">{c.score}/10</span>
                      </div>
                      {c.evidence_quote && (
                        <p className="ml-5.5 mt-1 flex gap-1.5 text-xs italic text-fg-3"><Quote className="size-3 shrink-0" />“{c.evidence_quote}”</p>
                      )}
                    </li>
                  ))}
                </ul>
                {(q.strengths.length > 0 || q.improvements.length > 0) && (
                  <div className="flex flex-wrap gap-1.5">
                    {q.strengths.map((s) => <Badge key={s} tone="good">{s}</Badge>)}
                    {q.improvements.map((s) => <Badge key={s} tone="warn">{s}</Badge>)}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </Card>

      <BiasAuditCard ev={ev} />

      <Card>
        <CardHeader icon={<FileJson />} title="Explainability trace" description="Complete, machine-readable record of models, weights, inputs and fairness checks behind this decision" />
        <CardBody>
          <pre className="max-h-80 overflow-auto rounded-lg border border-line bg-surface-2 p-3 font-mono text-[11px] leading-relaxed text-fg-2">
            {JSON.stringify(ev.audit_trace, null, 2)}
          </pre>
        </CardBody>
      </Card>
    </div>
  )
}
