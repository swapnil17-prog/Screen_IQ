import { forwardRef, useId, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes } from 'react'
import { ChevronDown } from 'lucide-react'
import { cn } from '@/lib/utils'

const control =
  'w-full rounded-lg border border-line-strong bg-surface text-sm text-fg placeholder:text-fg-3 shadow-card transition-[border-color,box-shadow] outline-none focus:border-brand focus:ring-[3px] focus:ring-[var(--ring)] disabled:opacity-60 aria-[invalid=true]:border-bad'

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(function Input(
  { className, ...props },
  ref,
) {
  return <input ref={ref} className={cn(control, 'h-9 px-3', className)} {...props} />
})

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(function Textarea(
  { className, ...props },
  ref,
) {
  return <textarea ref={ref} className={cn(control, 'min-h-24 px-3 py-2 leading-relaxed', className)} {...props} />
})

export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(function Select(
  { className, children, ...props },
  ref,
) {
  return (
    <div className="relative">
      <select ref={ref} className={cn(control, 'h-9 appearance-none pl-3 pr-8', className)} {...props}>
        {children}
      </select>
      <ChevronDown className="pointer-events-none absolute right-2.5 top-1/2 size-4 -translate-y-1/2 text-fg-3" />
    </div>
  )
})

export function Field({
  label,
  hint,
  error,
  children,
  className,
  htmlFor,
  optional,
}: {
  label: ReactNode
  hint?: ReactNode
  error?: string | null
  children: ReactNode | ((id: string) => ReactNode)
  className?: string
  htmlFor?: string
  optional?: boolean
}) {
  const autoId = useId()
  const id = htmlFor ?? autoId
  return (
    <div className={cn('space-y-1.5', className)}>
      <label htmlFor={id} className="flex items-center gap-1.5 text-[13px] font-medium text-fg">
        {label}
        {optional && <span className="font-normal text-fg-3">(optional)</span>}
      </label>
      {typeof children === 'function' ? children(id) : children}
      {error ? (
        <p className="text-xs text-bad-text" role="alert">{error}</p>
      ) : hint ? (
        <p className="text-xs text-fg-3">{hint}</p>
      ) : null}
    </div>
  )
}
