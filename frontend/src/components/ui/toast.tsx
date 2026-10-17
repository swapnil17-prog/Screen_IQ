import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { CircleAlert, CircleCheck, Info, X } from 'lucide-react'
import { cn } from '@/lib/utils'

type ToastTone = 'success' | 'error' | 'info'
interface Toast {
  id: number
  tone: ToastTone
  title: string
  description?: string
}

interface ToastApi {
  success: (title: string, description?: string) => void
  error: (title: string, description?: string) => void
  info: (title: string, description?: string) => void
}

const ToastContext = createContext<ToastApi | null>(null)
let nextId = 1

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])

  const dismiss = useCallback((id: number) => setToasts((t) => t.filter((x) => x.id !== id)), [])
  const push = useCallback(
    (tone: ToastTone, title: string, description?: string) => {
      const id = nextId++
      setToasts((t) => [...t.slice(-3), { id, tone, title, description }])
      setTimeout(() => dismiss(id), tone === 'error' ? 7000 : 4000)
    },
    [dismiss],
  )

  const api = useMemo<ToastApi>(
    () => ({
      success: (t, d) => push('success', t, d),
      error: (t, d) => push('error', t, d),
      info: (t, d) => push('info', t, d),
    }),
    [push],
  )

  return (
    <ToastContext.Provider value={api}>
      {children}
      {createPortal(
        <div className="pointer-events-none fixed bottom-4 right-4 z-[60] flex w-[calc(100%-2rem)] max-w-sm flex-col gap-2" aria-live="polite">
          {toasts.map((t) => {
            const Icon = t.tone === 'success' ? CircleCheck : t.tone === 'error' ? CircleAlert : Info
            return (
              <div
                key={t.id}
                role={t.tone === 'error' ? 'alert' : 'status'}
                className="pointer-events-auto flex animate-slide-up items-start gap-3 rounded-xl border border-line bg-surface p-3.5 shadow-pop"
              >
                <Icon
                  className={cn(
                    'mt-0.5 size-4 shrink-0',
                    t.tone === 'success' && 'text-good',
                    t.tone === 'error' && 'text-bad',
                    t.tone === 'info' && 'text-brand',
                  )}
                />
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-fg">{t.title}</p>
                  {t.description && <p className="mt-0.5 text-[13px] text-fg-2">{t.description}</p>}
                </div>
                <button onClick={() => dismiss(t.id)} className="text-fg-3 hover:text-fg" aria-label="Dismiss">
                  <X className="size-4" />
                </button>
              </div>
            )
          })}
        </div>,
        document.body,
      )}
    </ToastContext.Provider>
  )
}

export function useToast(): ToastApi {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used inside <ToastProvider>')
  return ctx
}
