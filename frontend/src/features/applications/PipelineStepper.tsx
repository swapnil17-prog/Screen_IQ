import { Check, CircleAlert } from 'lucide-react'
import type { ApplicationDetail } from '@/lib/types'
import { cn } from '@/lib/utils'
import { Spinner } from '@/components/ui/misc'

type StepState = 'done' | 'active' | 'todo' | 'failed'

const ORDER = ['queued', 'extracting', 'analyzing', 'matching', 'scoring', 'completed']

/** Resume → Parser → Skill Extraction → Experience Analysis → JD Matching → Candidate Score → AI Interview → Final Evaluation */
export function PipelineStepper({ app, className }: { app: ApplicationDetail; className?: string }) {
  const idx = ORDER.indexOf(app.status === 'parsing' ? 'extracting' : app.status)
  const screened = app.status === 'completed'
  const screeningStep = (at: number): StepState => {
    if (screened || idx > at) return 'done'
    return idx === at ? 'active' : 'todo'
  }
  const iv = app.interview
  const ev = app.evaluation

  const steps: { label: string; state: StepState }[] = [
    { label: 'Resume parsed', state: screeningStep(1) },
    { label: 'Skills extracted', state: screeningStep(1) },
    { label: 'Experience analysis', state: screeningStep(2) },
    { label: 'JD matching (RAG)', state: screeningStep(3) },
    { label: 'Candidate score', state: screeningStep(4) },
    {
      label: 'AI interview',
      state: iv?.status === 'completed' ? 'done' : iv && ['pending', 'in_progress'].includes(iv.status) ? 'active' : 'todo',
    },
    {
      label: 'Final evaluation',
      state: ev?.status === 'completed' ? 'done' : ev?.status === 'running' ? 'active' : ev?.status === 'failed' ? 'failed' : 'todo',
    },
  ]
  return (
    <ol className={cn('no-scrollbar flex items-center gap-1 overflow-x-auto pb-1', className)} aria-label="Hiring pipeline">
      {steps.map((s, i) => (
        <li key={s.label} className="flex shrink-0 items-center gap-1">
          <div
            className={cn(
              'flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium',
              s.state === 'done' && 'border-transparent bg-good-soft text-good-text',
              s.state === 'active' && 'border-[color-mix(in_oklab,var(--brand)_35%,transparent)] bg-brand-soft text-brand-text',
              s.state === 'todo' && 'border-line bg-surface text-fg-3',
              s.state === 'failed' && 'border-transparent bg-bad-soft text-bad-text',
            )}
          >
            {s.state === 'done' && <Check className="size-3" />}
            {s.state === 'active' && <Spinner className="size-3" />}
            {s.state === 'failed' && <CircleAlert className="size-3" />}
            {s.label}
          </div>
          {i < steps.length - 1 && <span className="h-px w-3 bg-line-strong" aria-hidden />}
        </li>
      ))}
    </ol>
  )
}
