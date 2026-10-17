import { useEffect, useRef, useState, type FormEvent } from 'react'
import { useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowUp, Bot, CheckCircle2, Clock, Lock, MessageSquareText, ShieldCheck } from 'lucide-react'
import { api, ApiError } from '@/lib/api'
import type { ChatMessage, PublicInterview } from '@/lib/types'
import { cn, errorMessage } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { PageLoader, ProgressBar } from '@/components/ui/misc'
import { Logo } from '@/components/layout/Logo'

const MAX = 4000

function Shell({ children, header }: { children: React.ReactNode; header?: React.ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col bg-page">
      <header className="sticky top-0 z-10 border-b border-line bg-page/90 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-3xl items-center justify-between gap-4 px-4">
          <Logo />
          {header}
        </div>
      </header>
      {children}
    </div>
  )
}

function Notice({ icon, title, text }: { icon: React.ReactNode; title: string; text: string }) {
  return (
    <Shell>
      <div className="mx-auto flex w-full max-w-md flex-1 flex-col items-center justify-center px-6 text-center">
        <div className="flex size-12 items-center justify-center rounded-full bg-surface-3 text-fg-2 [&_svg]:size-5">{icon}</div>
        <h1 className="mt-4 text-lg font-semibold text-fg">{title}</h1>
        <p className="mt-2 text-sm text-fg-2">{text}</p>
      </div>
    </Shell>
  )
}

function Welcome({ token, iv }: { token: string; iv: PublicInterview }) {
  const qc = useQueryClient()
  const [agree, setAgree] = useState(false)
  const start = useMutation({
    mutationFn: () => api.startPublicInterview(token),
    onSuccess: (data) => qc.setQueryData(['public-interview', token], data),
  })
  return (
    <Shell>
      <main className="mx-auto w-full max-w-xl flex-1 px-4 py-10 sm:py-16">
        <p className="text-[13px] font-medium text-brand-text">{iv.organization_name}</p>
        <h1 className="mt-2 text-2xl font-semibold tracking-[-0.02em] text-fg sm:text-3xl">
          {iv.candidate_first_name ? `Hi ${iv.candidate_first_name}, welcome` : 'Welcome'} to your interview for {iv.job_title}
        </h1>
        <p className="mt-3 text-[15px] leading-relaxed text-fg-2">
          This is a short, written interview conducted by an AI interviewer. It’s tailored to your background and the role.
        </p>
        <div className="mt-6 grid grid-cols-3 gap-3">
          {[
            [<MessageSquareText key="q" />, `${iv.question_count} questions`],
            [<Clock key="c" />, `~${iv.estimated_minutes} minutes`],
            [<Lock key="l" />, 'Private link'],
          ].map(([icon, label], i) => (
            <div key={i} className="flex flex-col items-center gap-1.5 rounded-xl border border-line bg-surface p-3 text-center text-[13px] text-fg-2 [&_svg]:size-4 [&_svg]:text-brand-text">
              {icon}{label}
            </div>
          ))}
        </div>
        <Card className="mt-6 p-5">
          <h2 className="text-sm font-semibold text-fg">Tips for a great interview</h2>
          <ul className="mt-2 space-y-1.5 text-[13px] text-fg-2">
            <li>• Answer in your own words — there are no trick questions.</li>
            <li>• Specific examples (what you did, why, and the outcome) help most.</li>
            <li>• The interviewer may ask a brief follow-up to learn more.</li>
            <li>• You can leave and return with the same link until it expires.</li>
          </ul>
        </Card>
        <label className="mt-6 flex cursor-pointer items-start gap-3 rounded-xl border border-line bg-surface p-4 text-[13px] text-fg-2">
          <input type="checkbox" checked={agree} onChange={(e) => setAgree(e.target.checked)} className="mt-0.5 size-4 accent-[var(--brand)]" />
          <span>
            I understand that this interview is conducted by an AI system, that my answers are recorded, and that they’ll be reviewed by
            the hiring team together with an AI-generated assessment. Hiring decisions are made by people.
          </span>
        </label>
        {start.error && <p className="mt-3 text-sm text-bad-text">{errorMessage(start.error)}</p>}
        <Button size="lg" className="mt-5 w-full" disabled={!agree} loading={start.isPending} onClick={() => start.mutate()}>
          Start interview
        </Button>
        <p className="mt-4 flex items-center justify-center gap-1.5 text-xs text-fg-3"><ShieldCheck className="size-3.5" />Your responses are shared only with {iv.organization_name}.</p>
      </main>
    </Shell>
  )
}

function Bubble({ m }: { m: ChatMessage }) {
  const bot = m.role === 'assistant'
  return (
    <div className={cn('flex animate-slide-up gap-3', !bot && 'flex-row-reverse')}>
      {bot && <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-brand-soft text-brand-text"><Bot className="size-4" /></div>}
      <div
        className={cn(
          'max-w-[85%] whitespace-pre-wrap rounded-2xl px-4 py-3 text-[15px] leading-relaxed',
          bot ? 'rounded-tl-md border border-line bg-surface text-fg shadow-card' : 'rounded-tr-md bg-brand text-brand-fg',
          m.kind === 'question' && 'font-medium',
        )}
      >
        {m.content}
      </div>
    </div>
  )
}

function Chat({ token, iv }: { token: string; iv: PublicInterview }) {
  const qc = useQueryClient()
  const [messages, setMessages] = useState<ChatMessage[]>(iv.messages)
  const [draft, setDraft] = useState('')
  const [progress, setProgress] = useState({ answered: iv.answered_questions, total: iv.question_count })
  const [done, setDone] = useState(iv.status === 'completed')
  const [error, setError] = useState<string | null>(null)
  const end = useRef<HTMLDivElement>(null)
  const box = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    end.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages.length])

  const send = useMutation({
    mutationFn: (text: string) => api.sendPublicMessage(token, text),
    onMutate: (text) => {
      setError(null)
      setMessages((m) => [...m, { role: 'candidate', content: text, timestamp: new Date().toISOString(), question_id: null, kind: 'answer' }])
      setDraft('')
    },
    onSuccess: (res) => {
      setMessages((m) => [...m, ...res.new_messages])
      setProgress({ answered: res.answered_questions, total: res.question_count })
      if (res.completed) {
        setDone(true)
        qc.invalidateQueries({ queryKey: ['public-interview', token] })
      }
      setTimeout(() => box.current?.focus(), 50)
    },
    onError: (e, text) => {
      // Roll back the optimistic bubble and restore the draft so nothing is lost
      setMessages((m) => m.slice(0, -1))
      setDraft(text)
      if (e instanceof ApiError && e.status === 409) setDone(true)
      setError(errorMessage(e))
    },
  })

  function submit(e?: FormEvent) {
    e?.preventDefault()
    const text = draft.trim()
    if (!text || send.isPending || done) return
    send.mutate(text)
  }

  return (
    <Shell
      header={
        <div className="flex items-center gap-3">
          <span className="hidden text-xs text-fg-3 sm:inline">{done ? 'Complete' : `Question ${Math.min(progress.answered + 1, progress.total)} of ${progress.total}`}</span>
          <ProgressBar value={done ? 100 : (progress.answered / progress.total) * 100} className="w-24 sm:w-32" />
        </div>
      }
    >
      <main className="mx-auto w-full max-w-3xl flex-1 space-y-4 px-4 py-6">
        <div className="pb-2 text-center text-xs text-fg-3">{iv.organization_name} · {iv.job_title}</div>
        {messages.map((m, i) => <Bubble key={i} m={m} />)}
        {send.isPending && (
          <div className="flex gap-3">
            <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-brand-soft text-brand-text"><Bot className="size-4" /></div>
            <div className="flex items-center gap-1 rounded-2xl rounded-tl-md border border-line bg-surface px-4 py-3.5 shadow-card" aria-label="Interviewer is typing">
              {[0, 1, 2].map((i) => <span key={i} className="size-1.5 animate-bounce rounded-full bg-fg-3" style={{ animationDelay: `${i * 150}ms` }} />)}
            </div>
          </div>
        )}
        {done && (
          <div className="mt-8 animate-slide-up rounded-2xl border border-line bg-surface p-6 text-center shadow-card">
            <CheckCircle2 className="mx-auto size-10 text-good" />
            <h2 className="mt-3 text-lg font-semibold text-fg">Interview complete — thank you!</h2>
            <p className="mx-auto mt-1.5 max-w-md text-sm text-fg-2">Your responses have been shared with the {iv.organization_name} hiring team. They’ll be in touch about next steps. You can close this page.</p>
          </div>
        )}
        <div ref={end} />
      </main>

      {!done && (
        <div className="sticky bottom-0 border-t border-line bg-page/95 backdrop-blur">
          <form onSubmit={submit} className="mx-auto max-w-3xl px-4 py-3">
            {error && <p className="mb-2 text-sm text-bad-text" role="alert">{error}</p>}
            <div className="flex items-end gap-2 rounded-2xl border border-line-strong bg-surface p-2 shadow-card focus-within:border-brand focus-within:ring-[3px] focus-within:ring-[var(--ring)]">
              <textarea
                ref={box}
                value={draft}
                maxLength={MAX}
                autoFocus
                rows={Math.min(8, Math.max(2, draft.split('\n').length))}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); submit() } }}
                placeholder="Type your answer… (Enter to send, Shift+Enter for a new line)"
                aria-label="Your answer"
                className="max-h-60 flex-1 resize-none bg-transparent px-2 py-1.5 text-[15px] text-fg outline-none placeholder:text-fg-3"
              />
              <Button type="submit" size="icon" disabled={!draft.trim()} loading={send.isPending} aria-label="Send answer" className="rounded-xl">
                {!send.isPending && <ArrowUp />}
              </Button>
            </div>
            <div className="mt-1.5 flex justify-between px-1 text-[11px] text-fg-3">
              <span>Your answers are saved as you go.</span>
              <span className="tabular">{draft.length}/{MAX}</span>
            </div>
          </form>
        </div>
      )}
    </Shell>
  )
}

export function CandidateInterviewPage() {
  const { token = '' } = useParams()
  const { data, isLoading, error } = useQuery({
    queryKey: ['public-interview', token],
    queryFn: () => api.publicInterview(token),
    retry: false,
    refetchOnWindowFocus: false,
  })

  if (isLoading) return <PageLoader label="Loading your interview…" />
  if (error || !data) {
    return <Notice icon={<Lock />} title="This link isn’t valid" text={errorMessage(error, 'Please check the link or contact the recruiter who sent it.')} />
  }
  if (data.status === 'expired') {
    return <Notice icon={<Clock />} title="This interview link has expired" text="Please contact the recruiter for a new link." />
  }
  if (data.status === 'completed' && !data.consent_given) {
    return <Notice icon={<CheckCircle2 />} title="Interview complete" text="Thank you — your responses have been shared with the hiring team." />
  }
  if (!data.consent_given) return <Welcome token={token} iv={data} />
  return <Chat token={token} iv={data} />
}
