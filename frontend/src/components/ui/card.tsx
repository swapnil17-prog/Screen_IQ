import type { HTMLAttributes, ReactNode } from 'react'
import { cn } from '@/lib/utils'

export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('rounded-xl border border-line bg-surface shadow-card', className)} {...props} />
}

export function CardHeader({
  title,
  description,
  action,
  icon,
  className,
}: {
  title: ReactNode
  description?: ReactNode
  action?: ReactNode
  icon?: ReactNode
  className?: string
}) {
  return (
    <div className={cn('flex items-start gap-3 px-5 pt-4 pb-3', className)}>
      {icon && <div className="mt-0.5 text-fg-3 [&_svg]:size-4">{icon}</div>}
      <div className="min-w-0 flex-1">
        <h3 className="text-[14px] font-semibold tracking-[-0.01em] text-fg">{title}</h3>
        {description && <p className="mt-0.5 text-[13px] text-fg-3">{description}</p>}
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  )
}

export function CardBody({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('px-5 pb-5', className)} {...props} />
}

export function StatCard({
  label,
  value,
  hint,
  icon,
  className,
}: {
  label: string
  value: ReactNode
  hint?: ReactNode
  icon?: ReactNode
  className?: string
}) {
  return (
    <Card className={cn('p-4', className)}>
      <div className="flex items-center justify-between text-[13px] font-medium text-fg-2">
        {label}
        {icon && <span className="text-fg-3 [&_svg]:size-4">{icon}</span>}
      </div>
      <div className="mt-2 text-[26px] font-semibold leading-none tracking-[-0.02em] text-fg">{value}</div>
      {hint && <div className="mt-2 text-xs text-fg-3">{hint}</div>}
    </Card>
  )
}
