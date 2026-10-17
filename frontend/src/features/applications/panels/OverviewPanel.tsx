import { AlertTriangle, EyeOff } from 'lucide-react'
import type { ScreeningResult } from '@/lib/types'
import { titleCase } from '@/lib/format'
import { ContributionBar, seriesColor } from '@/components/charts/charts'
import { ProgressBar } from '@/components/ui/misc'

/** "Why this score?" — each component's score × weight, with the reasons behind it. */
export function ScoreExplanation({ s }: { s: ScreeningResult }) {
  const redacted = Object.values(s.redactions).reduce((a, b) => a + b, 0)
  return (
    <div className="space-y-5">
      <ContributionBar
        total={s.overall_score}
        parts={s.components.map((c) => ({ key: c.key, label: c.label, contribution: c.contribution, score: c.score, weight: c.weight }))}
      />
      <div className="grid gap-3 md:grid-cols-2">
        {s.components.map((c, i) => (
          <div key={c.key} className="rounded-lg border border-line bg-surface-2 p-4">
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-2 text-[13px] font-semibold text-fg">
                <span className="size-2.5 rounded-[3px]" style={{ background: seriesColor(i) }} />
                {c.label}
              </div>
              <div className="text-[13px] tabular">
                <span className="font-semibold text-fg">{Math.round(c.score)}</span>
                <span className="text-fg-3"> /100 · {Math.round(c.weight * 100)}%</span>
              </div>
            </div>
            <ProgressBar value={c.score} tone="seq" className="mt-2.5" />
            <ul className="mt-3 space-y-1.5">
              {c.reasons.map((r) => (
                <li key={r} className="flex gap-2 text-[13px] leading-snug text-fg-2">
                  <span className="mt-[7px] size-1 shrink-0 rounded-full bg-fg-3" />
                  {r}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
      {s.flags.length > 0 && (
        <div className="space-y-1.5 rounded-lg bg-warn-soft p-3">
          {s.flags.map((f) => (
            <p key={f} className="flex gap-2 text-[13px] text-warn-text"><AlertTriangle className="mt-0.5 size-3.5 shrink-0" />{f}</p>
          ))}
        </div>
      )}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-fg-3">
        {s.blind_screening && (
          <span className="inline-flex items-center gap-1.5">
            <EyeOff className="size-3.5" /> Blind screening: {redacted} identity signal{redacted === 1 ? '' : 's'} redacted before AI review
            {redacted > 0 && ` (${Object.entries(s.redactions).map(([k, v]) => `${titleCase(k)} ${v}`).join(', ')})`}
          </span>
        )}
        <span>Model: {s.llm_model}</span>
        <span>Embeddings: {s.embedding_provider}</span>
        <span>Confidence: {s.confidence}</span>
      </div>
    </div>
  )
}
