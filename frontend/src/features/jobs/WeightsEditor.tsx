import type { ScoringWeights } from '@/lib/types'
import { seriesColor } from '@/components/charts/charts'

const ROWS: { key: keyof ScoringWeights; label: string; help: string }[] = [
  { key: 'skills', label: 'Skills match', help: 'Coverage of required and nice-to-have skills (exact, alias, and semantic matches)' },
  { key: 'experience', label: 'Experience fit', help: 'Years vs. requirement, role relevance and seniority alignment' },
  { key: 'semantic', label: 'Semantic similarity', help: 'Embedding similarity between resume sections and the job description' },
  { key: 'assessment', label: 'AI evidence assessment', help: 'Per-requirement judgement over retrieved resume evidence (RAG)' },
]

export function WeightsEditor({
  value,
  onChange,
  disabled,
}: {
  value: ScoringWeights
  onChange: (w: ScoringWeights) => void
  disabled?: boolean
}) {
  const total = Object.values(value).reduce((a, b) => a + b, 0) || 1
  return (
    <div className="space-y-5">
      {ROWS.map((r, i) => (
        <div key={r.key}>
          <div className="flex items-center justify-between gap-4">
            <label htmlFor={`w-${r.key}`} className="flex items-center gap-2 text-[13px] font-medium text-fg">
              <span className="size-2.5 rounded-[3px]" style={{ background: seriesColor(i) }} />
              {r.label}
            </label>
            <span className="text-[13px] font-semibold text-fg tabular">{Math.round((value[r.key] / total) * 100)}%</span>
          </div>
          <p className="mb-2 mt-0.5 text-xs text-fg-3">{r.help}</p>
          <input
            id={`w-${r.key}`}
            type="range"
            min={0}
            max={1}
            step={0.05}
            value={value[r.key]}
            disabled={disabled}
            onChange={(e) => onChange({ ...value, [r.key]: Number(e.target.value) })}
            className="w-full accent-[var(--brand)]"
          />
        </div>
      ))}
      <p className="text-xs text-fg-3">Weights are normalized to 100%. The final score is the weighted sum of the four components.</p>
    </div>
  )
}
