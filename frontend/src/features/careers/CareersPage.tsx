import { useRef, useState, type FormEvent, type ReactNode } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useMutation, useQuery } from '@tanstack/react-query'
import { ArrowLeft, Briefcase, CheckCircle2, ChevronRight, FileUp, MapPin, SearchX } from 'lucide-react'
import { api } from '@/lib/api'
import type { CareerJob } from '@/lib/types'
import { timeAgo } from '@/lib/format'
import { cn, errorMessage } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Field, Input } from '@/components/ui/input'
import { EmptyState, PageLoader } from '@/components/ui/misc'
import { Logo } from '@/components/layout/Logo'

const MAX_MB = 10

function Shell({ orgName, slug, children }: { orgName?: string; slug: string; children: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col bg-page">
      <header className="border-b border-line bg-surface">
        <div className="mx-auto flex h-16 max-w-5xl items-center px-4 sm:px-6">
          <Link to={`/careers/${slug}`} className="text-[17px] font-semibold tracking-[-0.02em] text-fg hover:text-brand-text">
            {orgName ? `${orgName} careers` : 'Careers'}
          </Link>
        </div>
      </header>
      <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-8 sm:px-6 sm:py-12">{children}</main>
      <footer className="border-t border-line py-6">
        <div className="mx-auto flex max-w-5xl items-center justify-center gap-2 px-4 text-xs text-fg-3">
          Hiring powered by <Logo />
        </div>
      </footer>
    </div>
  )
}

function NotFound({ slug, text }: { slug: string; text: string }) {
  return (
    <Shell slug={slug}>
      <EmptyState className="min-h-[50vh]" icon={<SearchX />} title="Nothing here" description={text} />
    </Shell>
  )
}

function JobMeta({ job, className }: { job: CareerJob; className?: string }) {
  const parts = [job.department, job.employment_type].filter(Boolean)
  return (
    <div className={cn('flex flex-wrap items-center gap-x-4 gap-y-1 text-[13px] text-fg-2', className)}>
      {job.location && <span className="inline-flex items-center gap-1.5"><MapPin className="size-3.5 text-fg-3" />{job.location}</span>}
      {parts.length > 0 && <span className="inline-flex items-center gap-1.5"><Briefcase className="size-3.5 text-fg-3" />{parts.join(' · ')}</span>}
      <span className="text-fg-3">Posted {timeAgo(job.created_at)}</span>
    </div>
  )
}

export function CareersPage() {
  const { slug = '' } = useParams()
  const { data, isLoading, error } = useQuery({ queryKey: ['careers', slug], queryFn: () => api.careers(slug), retry: false })
  if (isLoading) return <PageLoader />
  if (error || !data) return <NotFound slug={slug} text={errorMessage(error)} />

  return (
    <Shell orgName={data.organization_name} slug={slug}>
      <h1 className="text-3xl font-semibold tracking-[-0.03em] text-fg sm:text-4xl">Join {data.organization_name}</h1>
      <p className="mt-2 text-[15px] text-fg-2">
        {data.jobs.length ? `${data.jobs.length} open role${data.jobs.length === 1 ? '' : 's'}. Find the one that fits you.` : 'There are no open roles right now. Check back soon.'}
      </p>
      {data.jobs.length > 0 && (
        <ul className="mt-8 space-y-3">
          {data.jobs.map((job) => (
            <li key={job.id}>
              <Link to={`/careers/${slug}/jobs/${job.id}`} className="group block">
                <Card className="flex items-center gap-4 p-5 transition-colors group-hover:border-[color-mix(in_oklab,var(--brand)_40%,var(--line))]">
                  <div className="min-w-0 flex-1">
                    <h2 className="text-[16px] font-semibold text-fg group-hover:text-brand-text">{job.title}</h2>
                    <JobMeta job={job} className="mt-1.5" />
                  </div>
                  <ChevronRight className="size-5 shrink-0 text-fg-3 group-hover:text-brand-text" />
                </Card>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </Shell>
  )
}

function ApplyForm({ slug, jobId, orgName, jobTitle }: { slug: string; jobId: string; orgName: string; jobTitle: string }) {
  const fileRef = useRef<HTMLInputElement>(null)
  const [form, setForm] = useState({ full_name: '', email: '', phone: '', website: '' })
  const [file, setFile] = useState<File | null>(null)
  const [consent, setConsent] = useState(false)
  const [fileError, setFileError] = useState<string | null>(null)

  const apply = useMutation({
    mutationFn: () => {
      const body = new FormData()
      Object.entries(form).forEach(([k, v]) => v && body.append(k, v))
      body.append('consent', String(consent))
      body.append('resume', file!)
      return api.applyToJob(slug, jobId, body)
    },
  })

  function pick(f: File | undefined) {
    setFileError(null)
    if (!f) return setFile(null)
    if (!/\.(pdf|docx|txt)$/i.test(f.name)) return setFileError('Upload a PDF, DOCX or TXT file.')
    if (f.size > MAX_MB * 1024 * 1024) return setFileError(`Your resume must be under ${MAX_MB} MB.`)
    setFile(f)
  }

  function submit(e: FormEvent) {
    e.preventDefault()
    if (!file) return setFileError('Attach your resume.')
    apply.mutate()
  }

  if (apply.isSuccess) {
    return (
      <div className="flex flex-col items-center px-2 py-6 text-center">
        <span className="flex size-12 items-center justify-center rounded-full bg-good-soft text-good-text"><CheckCircle2 className="size-6" /></span>
        <h2 className="mt-4 text-lg font-semibold text-fg">Application sent</h2>
        <p className="mt-2 text-sm text-fg-2">
          Thanks for applying for {jobTitle}. The {orgName} hiring team will review your application and email you at {form.email} about next steps.
        </p>
        <Link to={`/careers/${slug}`} className="mt-5 text-sm font-medium text-brand-text hover:underline">See other open roles</Link>
      </div>
    )
  }

  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) => setForm({ ...form, [k]: e.target.value })
  return (
    <form onSubmit={submit} className="space-y-4">
      <h2 className="text-[17px] font-semibold text-fg">Apply for this role</h2>
      <Field label="Full name">{(id) => <Input id={id} required autoComplete="name" maxLength={120} value={form.full_name} onChange={set('full_name')} />}</Field>
      <Field label="Email">{(id) => <Input id={id} type="email" required autoComplete="email" value={form.email} onChange={set('email')} />}</Field>
      <Field label="Phone" optional>{(id) => <Input id={id} type="tel" autoComplete="tel" maxLength={40} value={form.phone} onChange={set('phone')} />}</Field>
      {/* Honeypot: invisible to people, tempting to bots */}
      <input type="text" name="website" tabIndex={-1} autoComplete="off" value={form.website} onChange={set('website')} className="absolute -left-[9999px] h-px w-px opacity-0" aria-hidden />
      <Field label="Resume" error={fileError} hint={file ? undefined : `PDF, DOCX or TXT, up to ${MAX_MB} MB`}>
        {(id) => (
          <>
            <input id={id} ref={fileRef} type="file" accept=".pdf,.docx,.txt" className="sr-only" onChange={(e) => pick(e.target.files?.[0])} />
            <button type="button" onClick={() => fileRef.current?.click()}
              className={cn('flex w-full items-center gap-3 rounded-lg border border-dashed border-line-strong bg-surface-2 px-3 py-3 text-left text-sm transition-colors hover:border-brand',
                fileError && 'border-bad')}>
              <FileUp className="size-5 shrink-0 text-brand-text" />
              <span className={cn('min-w-0 truncate', file ? 'font-medium text-fg' : 'text-fg-2')}>{file ? file.name : 'Choose a file'}</span>
              {file && <span className="ml-auto shrink-0 text-xs text-fg-3">Change</span>}
            </button>
          </>
        )}
      </Field>
      <label className="flex cursor-pointer items-start gap-3 text-[13px] leading-relaxed text-fg-2">
        <input type="checkbox" required checked={consent} onChange={(e) => setConsent(e.target.checked)} className="mt-0.5 size-4 shrink-0 accent-[var(--brand)]" />
        <span>
          I agree that {orgName} may process my resume and details to assess my application, including AI-assisted screening
          that is reviewed by people on the hiring team.
        </span>
      </label>
      {apply.error && <p className="rounded-lg bg-bad-soft px-3 py-2 text-sm text-bad-text" role="alert">{errorMessage(apply.error)}</p>}
      <Button type="submit" size="lg" className="w-full" loading={apply.isPending} disabled={!consent}>Submit application</Button>
    </form>
  )
}

export function CareerJobPage() {
  const { slug = '', jobId = '' } = useParams()
  const { data: job, isLoading, error } = useQuery({
    queryKey: ['career-job', slug, jobId],
    queryFn: () => api.careerJob(slug, jobId),
    retry: false,
  })
  if (isLoading) return <PageLoader />
  if (error || !job) return <NotFound slug={slug} text={errorMessage(error)} />

  return (
    <Shell orgName={job.organization_name} slug={slug}>
      <Link to={`/careers/${slug}`} className="inline-flex items-center gap-1.5 text-[13px] font-medium text-fg-2 hover:text-fg">
        <ArrowLeft className="size-4" /> All open roles
      </Link>
      <div className="mt-5 grid gap-8 lg:grid-cols-[1fr_380px] lg:items-start">
        <article className="min-w-0">
          <h1 className="text-3xl font-semibold tracking-[-0.03em] text-fg">{job.title}</h1>
          <JobMeta job={job} className="mt-3" />
          <div className="mt-8 whitespace-pre-wrap text-[15px] leading-relaxed text-fg">{job.description}</div>
        </article>
        <Card className="p-5 lg:sticky lg:top-6">
          <ApplyForm slug={slug} jobId={job.id} orgName={job.organization_name} jobTitle={job.title} />
        </Card>
      </div>
    </Shell>
  )
}
