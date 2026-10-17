import type { PipelineStatus, Recommendation, ScreeningLabel, Stage, Tier } from './types'

export function score(value: number | null | undefined, digits = 0): string {
  return value === null || value === undefined ? '—' : value.toFixed(digits)
}

export function pct(value: number | null | undefined): string {
  return value === null || value === undefined ? '—' : `${Math.round(value)}%`
}

export function years(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  return `${value % 1 === 0 ? value.toFixed(0) : value.toFixed(1)} yr${value === 1 ? '' : 's'}`
}

const rtf = new Intl.RelativeTimeFormat(undefined, { numeric: 'auto' })

export function timeAgo(iso: string | null | undefined): string {
  if (!iso) return '—'
  const diff = (new Date(iso).getTime() - Date.now()) / 1000
  const abs = Math.abs(diff)
  if (abs < 45) return 'just now'
  if (abs < 3600) return rtf.format(Math.round(diff / 60), 'minute')
  if (abs < 86400) return rtf.format(Math.round(diff / 3600), 'hour')
  if (abs < 86400 * 30) return rtf.format(Math.round(diff / 86400), 'day')
  return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
}

export function date(iso: string | null | undefined): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
}

export function dateTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })
}

export function monthYear(ym: string | null | undefined): string {
  if (!ym) return 'Present'
  const [y, m] = ym.split('-').map(Number)
  if (!y) return ym
  return new Date(y, (m || 1) - 1, 1).toLocaleDateString(undefined, { month: 'short', year: 'numeric' })
}

export function months(n: number | null | undefined): string {
  if (!n) return '—'
  const y = Math.floor(n / 12)
  const m = n % 12
  return [y ? `${y} yr${y > 1 ? 's' : ''}` : '', m ? `${m} mo` : ''].filter(Boolean).join(' ') || '<1 mo'
}

export function initials(name: string | null | undefined): string {
  if (!name) return '?'
  const parts = name.trim().split(/\s+/)
  return ((parts[0]?.[0] ?? '') + (parts.length > 1 ? parts[parts.length - 1][0] : '')).toUpperCase()
}

export function titleCase(s: string): string {
  return s.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
}

export const STAGES: { key: Stage; label: string }[] = [
  { key: 'new', label: 'New' },
  { key: 'shortlisted', label: 'Shortlisted' },
  { key: 'interviewing', label: 'Interviewing' },
  { key: 'offer', label: 'Offer' },
  { key: 'hired', label: 'Hired' },
  { key: 'rejected', label: 'Rejected' },
]

export const LABELS: Record<ScreeningLabel, string> = {
  strong_match: 'Strong match',
  good_match: 'Good match',
  potential: 'Potential',
  weak_match: 'Weak match',
}

export const RECOMMENDATIONS: Record<Recommendation, string> = {
  strong_hire: 'Strong hire',
  hire: 'Hire',
  lean_hire: 'Lean hire',
  lean_no_hire: 'Lean no hire',
  no_hire: 'No hire',
}

export type Tone = 'neutral' | 'brand' | 'good' | 'warn' | 'bad'

export function scoreTone(value: number | null | undefined): Tone {
  if (value === null || value === undefined) return 'neutral'
  if (value >= 75) return 'good'
  if (value >= 55) return 'warn'
  return 'bad'
}

export function recommendationTone(r: Recommendation | null | undefined): Tone {
  if (!r) return 'neutral'
  if (r === 'strong_hire' || r === 'hire') return 'good'
  if (r === 'lean_hire') return 'brand'
  if (r === 'lean_no_hire') return 'warn'
  return 'bad'
}

export const PIPELINE_STEPS: { key: PipelineStatus; label: string }[] = [
  { key: 'queued', label: 'Queued' },
  { key: 'extracting', label: 'Parsing & skill extraction' },
  { key: 'analyzing', label: 'Experience analysis' },
  { key: 'matching', label: 'JD matching & RAG' },
  { key: 'scoring', label: 'Scoring' },
  { key: 'completed', label: 'Screened' },
]

export const PROCESSING: PipelineStatus[] = ['queued', 'parsing', 'extracting', 'analyzing', 'matching', 'scoring']

export function isProcessing(status: PipelineStatus | string | null | undefined): boolean {
  return !!status && (PROCESSING as string[]).includes(status)
}

export function pipelineLabel(status: PipelineStatus): string {
  return PIPELINE_STEPS.find((s) => s.key === status)?.label ?? titleCase(status)
}

export const ACTION_LABELS: Record<string, string> = {
  'organization.created': 'created the workspace',
  'organization.updated': 'updated workspace settings',
  'job.created': 'created a job',
  'job.updated': 'updated a job',
  'job.deleted': 'deleted a job',
  'job.rescored': 're-scored a job',
  'applications.uploaded': 'uploaded resumes',
  'application.created': 'added a candidate to a job',
  'application.screened': 'screened a candidate',
  'application.stage_changed': 'moved a candidate',
  'interview.created': 'generated an AI interview',
  'interview.link_regenerated': 'issued a new interview link',
  'interview.cancelled': 'cancelled an interview',
  'interview.invite_sent': 'emailed an interview invitation',
  'application.applied': 'applied through the careers page',
  'notification.sent': 'sent an email notification',
  'notification.failed': 'couldn’t send an email notification',
  'user.password_reset_requested': 'requested a password reset',
  'user.password_reset': 'reset their password',
  'user.invite_accepted': 'accepted their invitation',
  'interview.invite_failed': 'couldn’t email an interview invitation',
  'interview.started': 'started an interview',
  'interview.completed': 'completed an interview',
  'evaluation.requested': 'requested an evaluation',
  'evaluation.completed': 'finished an evaluation',
  'candidate.erased': 'erased candidate data',
  'user.invited': 'invited a teammate',
  'user.updated': 'updated a teammate',
  'user.login': 'signed in',
  'user.password_changed': 'changed their password',
}

export const TIER_LABELS: Record<Tier, string> = {
  strong: 'Strong match',
  review: 'Needs review',
  low: 'Low fit',
}

/** Mirrors backend app.services.scoring.tier_for */
export function tierFor(score: number | null | undefined): Tier | null {
  if (score === null || score === undefined) return null
  if (score >= 80) return 'strong'
  if (score >= 60) return 'review'
  return 'low'
}

/** 38 → "38s", 130 → "2m 10s" */
export function duration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return '—'
  const s = Math.abs(Math.round(seconds))
  if (s < 60) return `${s}s`
  if (s < 3600) return `${Math.floor(s / 60)}m ${s % 60}s`
  return `${Math.floor(s / 3600)}h ${Math.floor((s % 3600) / 60)}m`
}
