import { useState } from 'react'
import { Check, ClipboardCopy, ExternalLink } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Button } from './button'

/** Inline "Copy link · Open" text actions for a shareable URL. */
export function CopyLink({ url, label = 'Copy link' }: { url: string; label?: string }) {
  const [copied, setCopied] = useState(false)
  return (
    <span className="inline-flex items-center gap-2 whitespace-nowrap">
      <button type="button" className="font-medium text-brand-text hover:underline"
        onClick={() => navigator.clipboard.writeText(url).then(() => { setCopied(true); setTimeout(() => setCopied(false), 1800) })}>
        {copied ? 'Copied' : label}
      </button>
      <span aria-hidden className="text-fg-3">·</span>
      <a href={url} target="_blank" rel="noreferrer" className="font-medium text-brand-text hover:underline">Open</a>
    </span>
  )
}

/** A read-only URL field with Copy and Open buttons. */
export function LinkBox({ url, title, className }: { url: string; title?: string; className?: string }) {
  const [copied, setCopied] = useState(false)
  return (
    <div className={cn('rounded-lg border border-[color-mix(in_oklab,var(--brand)_30%,transparent)] bg-brand-soft p-3', className)}>
      {title && <div className="mb-1.5 text-xs font-medium text-brand-text">{title}</div>}
      <div className="flex items-center gap-2">
        <code className="min-w-0 flex-1 truncate rounded-md bg-surface px-2.5 py-1.5 font-mono text-xs text-fg">{url}</code>
        <Button size="sm" variant="secondary" type="button"
          onClick={() => navigator.clipboard.writeText(url).then(() => { setCopied(true); setTimeout(() => setCopied(false), 1800) })}>
          {copied ? <Check /> : <ClipboardCopy />}{copied ? 'Copied' : 'Copy'}
        </Button>
        <a href={url} target="_blank" rel="noreferrer" className="inline-flex size-8 shrink-0 items-center justify-center rounded-lg text-fg-2 hover:bg-surface" aria-label="Open link">
          <ExternalLink className="size-4" />
        </a>
      </div>
    </div>
  )
}
