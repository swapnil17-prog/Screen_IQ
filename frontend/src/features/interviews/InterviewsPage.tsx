import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { MessagesSquare } from 'lucide-react'
import { api } from '@/lib/api'
import type { InterviewStatus } from '@/lib/types'
import { RECOMMENDATIONS, date, recommendationTone, timeAgo } from '@/lib/format'
import { PageHeader } from '@/components/layout/AppShell'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Segmented } from '@/components/ui/tabs'
import { Avatar, EmptyState, PageLoader, ProgressBar } from '@/components/ui/misc'

const STATUS: Record<InterviewStatus, { label: string; tone: 'neutral' | 'brand' | 'good' | 'warn' }> = {
  pending: { label: 'Not started', tone: 'neutral' },
  in_progress: { label: 'In progress', tone: 'brand' },
  completed: { label: 'Completed', tone: 'good' },
  expired: { label: 'Expired', tone: 'warn' },
  cancelled: { label: 'Cancelled', tone: 'neutral' },
}

export function InterviewsPage() {
  const [filter, setFilter] = useState<'all' | 'in_progress' | 'pending' | 'completed'>('all')
  const { data, isLoading } = useQuery({ queryKey: ['interviews'], queryFn: () => api.interviews(), refetchInterval: 15_000 })
  const items = (data ?? []).filter((i) => filter === 'all' || i.status === filter)

  return (
    <>
      <PageHeader title="AI interviews" description="Structured, gap-aware interviews conducted by the AI interviewer." />
      <Segmented
        className="mb-5"
        value={filter}
        onChange={setFilter}
        items={[
          { key: 'all', label: 'All' },
          { key: 'pending', label: 'Not started' },
          { key: 'in_progress', label: 'In progress' },
          { key: 'completed', label: 'Completed' },
        ]}
      />
      {isLoading ? <PageLoader /> : items.length === 0 ? (
        <Card>
          <EmptyState
            icon={<MessagesSquare />}
            title="No interviews here yet"
            description="Open a screened candidate and generate an AI interview to send them a private link."
          />
        </Card>
      ) : (
        <Card className="overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="text-[11px] font-medium uppercase tracking-wide text-fg-3">
                <th className="py-2.5 pl-5 pr-4 font-medium">Candidate</th>
                <th className="py-2.5 pr-4 font-medium">Status</th>
                <th className="hidden py-2.5 pr-4 font-medium md:table-cell">Progress</th>
                <th className="hidden py-2.5 pr-4 font-medium lg:table-cell">Timeline</th>
                <th className="py-2.5 pr-5 text-right font-medium">Result</th>
              </tr>
            </thead>
            <tbody>
              {items.map((i) => (
                <tr key={i.id} className="border-t border-line hover:bg-surface-2">
                  <td className="py-3 pl-5 pr-4">
                    <Link to={`/app/applications/${i.application_id}`} className="flex items-center gap-3">
                      <Avatar name={i.candidate_name} size="sm" />
                      <div className="min-w-0">
                        <div className="truncate text-sm font-medium text-fg hover:text-brand-text">{i.candidate_name ?? 'Unnamed'}</div>
                        <div className="truncate text-xs text-fg-3">{i.job_title}</div>
                      </div>
                    </Link>
                  </td>
                  <td className="py-3 pr-4"><Badge tone={STATUS[i.status].tone} dot>{STATUS[i.status].label}</Badge></td>
                  <td className="hidden py-3 pr-4 md:table-cell">
                    <div className="w-36">
                      <div className="mb-1 text-[11px] text-fg-3 tabular">{i.answered_questions}/{i.total_questions} answered</div>
                      <ProgressBar value={(i.answered_questions / Math.max(1, i.total_questions)) * 100} />
                    </div>
                  </td>
                  <td className="hidden py-3 pr-4 text-xs text-fg-3 lg:table-cell">
                    Sent {timeAgo(i.created_at)}<br />
                    {i.completed_at ? `Completed ${timeAgo(i.completed_at)}` : `Expires ${date(i.expires_at)}`}
                  </td>
                  <td className="py-3 pr-5 text-right">
                    {i.recommendation ? (
                      <Badge tone={recommendationTone(i.recommendation)}>{RECOMMENDATIONS[i.recommendation]} · {Math.round(i.final_score ?? 0)}</Badge>
                    ) : <span className="text-xs text-fg-3">—</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </>
  )
}
