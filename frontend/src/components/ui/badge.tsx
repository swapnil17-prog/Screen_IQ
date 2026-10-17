import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'
import type { Tone } from '@/lib/format'

const tones: Record<Tone, string> = {
  neutral: 'bg-surface-3 text-fg-2 ring-line',
  brand: 'bg-brand-soft text-brand-text ring-[color-mix(in_oklab,var(--brand)_25%,transparent)]',
  good: 'bg-good-soft text-good-text ring-[color-mix(in_oklab,var(--good)_25%,transparent)]',
  warn: 'bg-warn-soft text-warn-text ring-[color-mix(in_oklab,var(--warn)_35%,transparent)]',
  bad: 'bg-bad-soft text-bad-text ring-[color-mix(in_oklab,var(--bad)_25%,transparent)]',
}

const dots: Record<Tone, string> = {
  neutral: 'bg-fg-3',
  brand: 'bg-brand',
  good: 'bg-good',
  warn: 'bg-warn',
  bad: 'bg-bad',
}

export function Badge({
  tone = 'neutral',
  dot,
  icon,
  children,
  className,
}: {
  tone?: Tone
  dot?: boolean
  icon?: ReactNode
  children: ReactNode
  className?: string
}) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 whitespace-nowrap rounded-md px-2 py-0.5 text-xs font-medium ring-1 ring-inset [&_svg]:size-3',
        tones[tone],
        className,
      )}
    >
      {dot && <span className={cn('size-1.5 rounded-full', dots[tone])} />}
      {icon}
      {children}
    </span>
  )
}

export function Chip({ children, className, muted }: { children: ReactNode; className?: string; muted?: boolean }) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-md border border-line px-2 py-0.5 text-xs',
        muted ? 'bg-transparent text-fg-3' : 'bg-surface-2 text-fg-2',
        className,
      )}
    >
      {children}
    </span>
  )
}
