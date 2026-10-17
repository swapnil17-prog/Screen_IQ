import { useMemo } from 'react'
import { Download, FileText } from 'lucide-react'
import type { RequirementAssessment } from '@/lib/types'
import { cn } from '@/lib/utils'
import { Card } from '@/components/ui/card'

const norm = (s: string) => s.toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim()
const words = (s: string) => norm(s).split(' ').filter((w) => w.length > 2)

/**
 * The parsed resume as a document, with every line that the AI cited as
 * evidence for a met/partial requirement highlighted (hover shows which one).
 */
export function ResumePreview({ filename, text, requirements }: { filename: string; text: string; requirements: RequirementAssessment[] }) {
  const lines = useMemo(() => {
    const quotes = requirements
      .filter((r) => r.evidence_quote && r.verdict !== 'not_met')
      .map((r) => ({ q: norm(r.evidence_quote!), qw: new Set(words(r.evidence_quote!)), req: r.requirement }))
    return text.split('\n').map((line) => {
      const nl = norm(line)
      if (nl.length < 8) return { line, match: [] as string[] }
      const lw = words(line)
      // Short lines (section headers, bare titles) are too generic to count as evidence
      if (lw.length < 4) return { line, match: [] as string[] }
      const match = quotes
        .filter(({ q, qw }) => q.includes(nl) || nl.includes(q) || lw.filter((w) => qw.has(w)).length / lw.length >= 0.7)
        .map((m) => m.req)
      return { line, match }
    })
  }, [text, requirements])

  const highlighted = lines.filter((l) => l.match.length).length
  const firstContent = lines.findIndex((l) => l.line.trim())

  function download() {
    const url = URL.createObjectURL(new Blob([text], { type: 'text/plain;charset=utf-8' }))
    const a = document.createElement('a')
    a.href = url
    a.download = filename.replace(/\.[^.]+$/, '') + '.txt'
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <Card className="overflow-hidden">
      <div className="flex items-center gap-2 px-5 py-4">
        <FileText className="size-4 shrink-0 text-fg-3" />
        <span className="min-w-0 flex-1 truncate text-[15px] font-semibold text-fg">{filename}</span>
        <button onClick={download} className="rounded-md p-1.5 text-fg-3 hover:bg-surface-3 hover:text-fg" title="Download parsed text" aria-label="Download parsed text">
          <Download className="size-4" />
        </button>
      </div>
      <div className="bg-surface-3/70 px-5 py-5">
        <div className="max-h-[520px] overflow-y-auto rounded-sm bg-surface px-6 py-6 shadow-card">
          {lines.map(({ line, match }, i) =>
            line.trim() ? (
              <p
                key={i}
                title={match.length ? `Evidence for: ${match.join(', ')}` : undefined}
                className={cn(
                  '-mx-2 rounded px-2 py-px text-[12px] leading-relaxed',
                  i === firstContent ? 'mb-1 text-[15px] font-semibold text-fg' : 'text-fg-2',
                  match.length > 0 && 'bg-brand-soft text-fg',
                )}
              >
                {line}
              </p>
            ) : (
              <div key={i} className="h-2.5" />
            ),
          )}
        </div>
      </div>
      <div className="flex items-center gap-2 px-5 py-3 text-xs text-fg-3">
        <span className="size-2.5 rounded-[3px] bg-[color-mix(in_oklab,var(--brand)_40%,var(--brand-soft))]" />
        {highlighted ? `${highlighted} highlighted line${highlighted === 1 ? '' : 's'} matched your criteria` : 'No cited lines to highlight'}
      </div>
    </Card>
  )
}
