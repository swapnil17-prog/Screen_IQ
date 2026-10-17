import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

export interface TabItem<K extends string> {
  key: K
  label: ReactNode
  count?: number | null
  icon?: ReactNode
}

export function Tabs<K extends string>({
  items,
  value,
  onChange,
  className,
}: {
  items: TabItem<K>[]
  value: K
  onChange: (key: K) => void
  className?: string
}) {
  return (
    <div role="tablist" className={cn('no-scrollbar flex gap-1 overflow-x-auto overflow-y-hidden border-b border-line', className)}>
      {items.map((t) => {
        const active = t.key === value
        return (
          <button
            key={t.key}
            role="tab"
            type="button"
            aria-selected={active}
            onClick={() => onChange(t.key)}
            className={cn(
              'relative -mb-px flex items-center gap-2 whitespace-nowrap border-b-2 px-3 pb-2.5 pt-2 text-[13px] font-medium transition-colors [&_svg]:size-4',
              active ? 'border-brand text-fg' : 'border-transparent text-fg-3 hover:text-fg-2',
            )}
          >
            {t.icon}
            {t.label}
            {t.count !== undefined && t.count !== null && (
              <span className={cn('rounded-full px-1.5 text-[11px] tabular', active ? 'bg-brand-soft text-brand-text' : 'bg-surface-3 text-fg-3')}>
                {t.count}
              </span>
            )}
          </button>
        )
      })}
    </div>
  )
}

export function Segmented<K extends string>({
  items,
  value,
  onChange,
  className,
}: {
  items: { key: K; label: ReactNode }[]
  value: K
  onChange: (key: K) => void
  className?: string
}) {
  return (
    <div className={cn('inline-flex rounded-lg border border-line bg-surface-2 p-0.5', className)}>
      {items.map((it) => (
        <button
          key={it.key}
          type="button"
          aria-pressed={it.key === value}
          onClick={() => onChange(it.key)}
          className={cn(
            'whitespace-nowrap rounded-md px-2.5 py-1 text-xs font-medium transition-colors [&_svg]:size-3.5',
            it.key === value ? 'bg-surface text-fg shadow-card' : 'text-fg-3 hover:text-fg-2',
          )}
        >
          {it.label}
        </button>
      ))}
    </div>
  )
}
