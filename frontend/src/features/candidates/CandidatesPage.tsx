import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { Search, Sparkles, Users } from 'lucide-react'
import { api } from '@/lib/api'
import { timeAgo, years } from '@/lib/format'
import { PageHeader } from '@/components/layout/AppShell'
import { Card } from '@/components/ui/card'
import { Badge, Chip } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Segmented } from '@/components/ui/tabs'
import { Avatar, EmptyState, PageLoader, Spinner } from '@/components/ui/misc'

const PAGE = 25

export function CandidatesPage() {
  const [params] = useSearchParams()
  const initial = params.get('q') ?? ''
  const [mode, setMode] = useState<'keyword' | 'semantic'>('keyword')
  const [input, setInput] = useState(initial)
  const [q, setQ] = useState(initial)
  const [offset, setOffset] = useState(0)

  useEffect(() => {
    const t = setTimeout(() => { setQ(input.trim()); setOffset(0) }, mode === 'semantic' ? 500 : 250)
    return () => clearTimeout(t)
  }, [input, mode])

  const semantic = mode === 'semantic' && q.length > 0
  const { data, isLoading, isFetching } = useQuery({
    queryKey: ['candidates', q, mode, offset],
    queryFn: () => api.candidates({ q: q || undefined, semantic, limit: PAGE, offset }),
    placeholderData: keepPreviousData,
  })

  return (
    <>
      <PageHeader title="Candidates" description="Your talent pool — every candidate you've screened, searchable by keyword or by meaning." />
      <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative flex-1 sm:max-w-xl">
          {mode === 'semantic' ? <Sparkles className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-brand-text" /> : <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-fg-3" />}
          <Input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={mode === 'semantic' ? 'Describe who you’re looking for, e.g. “backend engineer who scaled Kafka pipelines”' : 'Search by name, email, title or skill…'}
            className="pl-9"
            aria-label="Search candidates"
          />
          {isFetching && <Spinner className="absolute right-3 top-1/2 size-4 -translate-y-1/2 text-fg-3" />}
        </div>
        <Segmented
          value={mode}
          onChange={(m) => { setMode(m); setOffset(0) }}
          items={[{ key: 'keyword', label: 'Keyword' }, { key: 'semantic', label: <span className="inline-flex items-center gap-1"><Sparkles />Semantic</span> }]}
        />
      </div>

      {isLoading ? <PageLoader /> : !data || data.items.length === 0 ? (
        <Card>
          <EmptyState
            icon={<Users />}
            title={q ? 'No matching candidates' : 'Your talent pool is empty'}
            description={q ? 'Try different wording or switch search mode.' : 'Candidates appear here after you upload resumes to a job.'}
          />
        </Card>
      ) : (
        <Card className="overflow-hidden">
          <ul className="divide-y divide-line">
            {data.items.map((c) => (
              <li key={c.id}>
                <Link to={`/app/candidates/${c.id}`} className="flex items-center gap-4 px-5 py-3.5 transition-colors hover:bg-surface-2">
                  <Avatar name={c.full_name} />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="truncate text-sm font-medium text-fg">{c.full_name ?? 'Unnamed candidate'}</span>
                      {c.status !== 'ready' && <Badge tone={c.status === 'failed' ? 'bad' : 'brand'}>{c.status}</Badge>}
                    </div>
                    <div className="truncate text-xs text-fg-3">{[c.headline, c.location, years(c.total_years)].filter((x) => x && x !== '—').join(' · ')}</div>
                    <div className="mt-1.5 hidden flex-wrap gap-1 md:flex">{c.skills.slice(0, 6).map((s) => <Chip key={s} className="py-0 text-[11px]">{s}</Chip>)}</div>
                  </div>
                  {c.similarity !== null && (
                    <div className="text-right">
                      <div className="text-sm font-semibold text-fg tabular">{Math.round(c.similarity)}%</div>
                      <div className="text-[11px] text-fg-3">relevance</div>
                    </div>
                  )}
                  <div className="hidden w-28 text-right text-xs text-fg-3 sm:block">
                    {c.applications_count} job{c.applications_count === 1 ? '' : 's'}<br />{timeAgo(c.created_at)}
                  </div>
                </Link>
              </li>
            ))}
          </ul>
          {!semantic && data.total > PAGE && (
            <div className="flex items-center justify-between border-t border-line px-5 py-3 text-[13px] text-fg-3">
              <span>{offset + 1}–{Math.min(offset + PAGE, data.total)} of {data.total}</span>
              <div className="flex gap-2">
                <Button variant="secondary" size="sm" disabled={offset === 0} onClick={() => setOffset(offset - PAGE)}>Previous</Button>
                <Button variant="secondary" size="sm" disabled={offset + PAGE >= data.total} onClick={() => setOffset(offset + PAGE)}>Next</Button>
              </div>
            </div>
          )}
        </Card>
      )}
      {semantic && <p className="mt-3 text-xs text-fg-3">Semantic search embeds your query and ranks candidates by vector similarity (pgvector) — it finds relevant profiles even when they use different words.</p>}
    </>
  )
}
