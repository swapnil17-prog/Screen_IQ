import { Check } from 'lucide-react'
import type { Stage, Tier } from '@/lib/types'
import { TIER_LABELS, tierFor } from '@/lib/format'
import { cn } from '@/lib/utils'

const TIER_BAR: Record<Tier, string> = {
  strong: 'bg-tier-strong',
  review: 'bg-tier-review',
  low: 'bg-tier-low',
}

const pill = 'inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-medium [&_svg]:size-3'

/** Status column: recruiter decisions win over the AI tier. */
export function StatusPill({ stage, tier, className }: { stage: Stage; tier: Tier | null; className?: string }) {
  if (stage === 'shortlisted') return <span className={cn(pill, 'bg-brand text-brand-fg', className)}><Check />Shortlisted</span>
  if (stage === 'interviewing') return <span className={cn(pill, 'bg-brand text-brand-fg', className)}>Interviewing</span>
  if (stage === 'offer') return <span className={cn(pill, 'bg-good-soft text-good-text', className)}>Offer</span>
  if (stage === 'hired') return <span className={cn(pill, 'bg-good-soft text-good-text', className)}><Check />Hired</span>
  if (stage === 'rejected') return <span className={cn(pill, 'border border-line text-fg-3', className)}>Rejected</span>
  return <TierPill tier={tier} className={className} />
}

export function TierPill({ tier, className }: { tier: Tier | null; className?: string }) {
  if (!tier) return null
  return (
    <span
      className={cn(
        pill,
        tier === 'strong' && 'bg-brand-soft text-brand-text',
        tier === 'review' && 'border border-line bg-surface-3 text-fg-2',
        tier === 'low' && 'bg-tier-low-soft text-tier-low-text',
        className,
      )}
    >
      {TIER_LABELS[tier]}
    </span>
  )
}

/** "94 ▬▬▬▬▬▬▬▬▬▬░" — number plus a bar colored by tier. */
export function ScoreBar({ value, className }: { value: number | null | undefined; className?: string }) {
  const tier = tierFor(value)
  return (
    <div className={cn('flex items-center gap-3', className)}>
      <span className="w-7 text-[15px] font-semibold text-fg tabular">{value === null || value === undefined ? '—' : Math.round(value)}</span>
      <div className="h-1.5 w-24 overflow-hidden rounded-full bg-track" aria-hidden>
        {tier && <div className={cn('h-full rounded-full', TIER_BAR[tier])} style={{ width: `${value}%` }} />}
      </div>
    </div>
  )
}

/** Stacked strong / review / low bar with a text breakdown (the text makes it readable without color). */
export function PipelineBar({ strong, review, low, className }: { strong: number; review: number; low: number; className?: string }) {
  const total = strong + review + low
  if (!total) return <span className="text-xs text-fg-3">Not screened yet</span>
  const pct = (n: number) => Math.round((n / total) * 100)
  return (
    <div className={cn('min-w-56', className)}>
      <div className="flex h-2 overflow-hidden rounded-full bg-track" role="img" aria-label={`${pct(strong)}% strong, ${pct(review)}% review, ${pct(low)}% low fit`}>
        {(['strong', 'review', 'low'] as const).map((t, i) => {
          const n = { strong, review, low }[t]
          return n ? <div key={t} className={cn('h-full', TIER_BAR[t], i > 0 && 'border-l-2 border-surface')} style={{ width: `${(n / total) * 100}%` }} /> : null
        })}
      </div>
      <div className="mt-1.5 whitespace-nowrap text-xs text-fg-3 tabular">
        {pct(strong)}% strong · {pct(review)}% review · {pct(low)}% low fit
      </div>
    </div>
  )
}

export function TierLegend({ className }: { className?: string }) {
  return (
    <div className={cn('flex flex-wrap items-center gap-x-5 gap-y-1 text-xs text-fg-2', className)}>
      {(['strong', 'review', 'low'] as const).map((t) => (
        <span key={t} className="inline-flex items-center gap-1.5">
          <span className={cn('size-2.5 rounded-[3px]', TIER_BAR[t])} />
          {TIER_LABELS[t]}
        </span>
      ))}
    </div>
  )
}

/** Must-have chips are solid ink, nice-to-haves outlined — as in the job header. */
export function CriteriaChip({ children, must }: { children: React.ReactNode; must?: boolean }) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-md px-2 py-0.5 text-[13px]',
        must ? 'bg-ink text-ink-fg' : 'border border-line-strong bg-surface text-fg-2',
      )}
    >
      {children}
    </span>
  )
}

/** Skill vs. criteria chip in the ranked table; missing skills are struck through in orange. */
export function SkillChip({ skill, status }: { skill: string; status: 'matched' | 'partial' | 'missing' }) {
  return (
    <span
      title={status === 'missing' ? `${skill}: not found on resume` : status === 'partial' ? `${skill}: partial evidence` : skill}
      className={cn(
        'inline-flex items-center whitespace-nowrap rounded-md px-1.5 py-0.5 text-xs',
        status === 'matched' && 'bg-brand-soft text-brand-text',
        status === 'partial' && 'border border-dashed border-[color-mix(in_oklab,var(--brand)_45%,transparent)] text-brand-text',
        status === 'missing' && 'bg-tier-low-soft text-tier-low-text line-through decoration-1',
      )}
    >
      {skill}
    </span>
  )
}
