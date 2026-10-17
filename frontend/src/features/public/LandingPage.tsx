import { Link } from 'react-router-dom'
import {
  ArrowRight,
  Check,
  EyeOff,
  FileText,
  MessagesSquare,
  ScanSearch,
  Scale,
  SlidersHorizontal,
} from 'lucide-react'
import { useAuth } from '@/hooks/useAuth'
import { ButtonLink } from '@/components/ui/button'
import { Logo } from '@/components/layout/Logo'
import { ScoreBar, TierPill } from '@/components/ui/tier'
import type { Tier } from '@/lib/types'

// Illustrative product preview (sample data, not real candidates)
const PREVIEW: { initials: string; name: string; role: string; score: number; summary: string; tier: Tier }[] = [
  { initials: 'AO', name: 'Ada Okafor', role: 'Senior Software Engineer', score: 93, summary: 'Meets all must-haves; led a Kubernetes migration.', tier: 'strong' },
  { initials: 'RS', name: 'Rahul Sen', role: 'Backend Engineer', score: 86, summary: 'Strong Python and PostgreSQL; owns payments APIs.', tier: 'strong' },
  { initials: 'BC', name: 'Ben Carter', role: 'Full Stack Developer', score: 71, summary: 'Solid APIs; missing Kubernetes and AWS.', tier: 'review' },
  { initials: 'CM', name: 'Chloe Martin', role: 'Marketing Coordinator', score: 38, summary: 'Different field; no core engineering skills.', tier: 'low' },
]

const STEPS = [
  { n: '01', title: 'Set your criteria', text: 'Paste a job description and ScreenIQ drafts must-have and nice-to-have criteria, and checks the wording for bias. Adjust criteria and weights to match how your team hires.' },
  { n: '02', title: 'Drop in resumes', text: 'Upload PDFs, Word files or text in bulk. Parsing, skill extraction and experience analysis start instantly.' },
  { n: '03', title: 'Review a ranked list', text: 'Every candidate gets a match score with cited evidence. Shortlist, reject or send an AI interview in one click, together with your team.' },
]

const FEATURES = [
  { icon: FileText, title: 'Smart resume parsing', text: 'Reads PDFs, Word and text files and pulls out skills, roles and dates — overlapping jobs are never double-counted.' },
  { icon: SlidersHorizontal, title: 'Weighted criteria', text: 'Mark what is essential and what is a bonus. Scores reflect the priorities your team agreed on.' },
  { icon: EyeOff, title: 'Blind screening', text: 'Names, contact details and demographic signals are masked before the AI assesses a resume or interview.' },
  { icon: ScanSearch, title: 'Semantic search & RAG', text: 'Every requirement retrieves real resume evidence. Search your talent pool by meaning, not keywords.' },
  { icon: MessagesSquare, title: 'AI interviews', text: 'Tailored, structured interviews that probe exactly what the resume left unproven — graded against a rubric.' },
  { icon: Scale, title: 'Fairness audits', text: 'Inclusive-language checks on job posts and counterfactual audits on every evaluation, with a full audit log.' },
]

const CRITERIA = [
  { ok: true, name: 'Python · must-have', detail: '8 yrs across Streamline and Brightpath' },
  { ok: true, name: 'Kubernetes · must-have', detail: 'Led the migration to EKS, 2023' },
  { ok: true, name: 'Apache Kafka · nice to have', detail: 'Built a 2B-events/month pipeline' },
  { ok: false, name: 'Terraform · nice to have', detail: 'Mentioned once — ask in interview' },
]

export function LandingPage() {
  const { me } = useAuth()
  const primary = me ? { to: '/app', label: 'Open dashboard' } : { to: '/register', label: 'Get started free' }

  return (
    <div className="min-h-screen bg-page">
      <header className="sticky top-0 z-20 border-b border-line bg-page/85 backdrop-blur">
        <div className="mx-auto flex h-[72px] max-w-6xl items-center justify-between px-5">
          <div className="flex items-center gap-10">
            <Logo />
            <nav className="hidden items-center gap-8 text-[15px] text-fg-2 md:flex">
              <a href="#how" className="hover:text-fg">How it works</a>
              <a href="#receipts" className="hover:text-fg">Explainability</a>
              <a href="#features" className="hover:text-fg">Features</a>
            </nav>
          </div>
          <div className="flex items-center gap-3">
            {!me && <Link to="/login" className="px-2 text-[15px] font-medium text-fg hover:text-brand-text">Log in</Link>}
            <Link to={primary.to} className="inline-flex h-10 items-center rounded-lg bg-ink px-4 text-sm font-semibold text-ink-fg hover:opacity-90">
              {me ? 'Open dashboard' : 'Get started'}
            </Link>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="mx-auto max-w-6xl px-5 pb-16 pt-20 text-center sm:pt-24">
        <span className="inline-flex rounded-full bg-brand-soft px-3.5 py-1.5 text-[13px] font-semibold text-brand-text">
          Explainable AI screening for hiring teams
        </span>
        <h1 className="mx-auto mt-7 max-w-5xl text-[44px] font-semibold leading-[1.02] tracking-[-0.045em] text-fg sm:text-[76px]">
          Read every resume.
          <br />
          <span className="font-serif font-normal italic tracking-[-0.02em] text-brand">Interview</span> only the right ones.
        </h1>
        <p className="mx-auto mt-6 max-w-2xl text-lg leading-relaxed text-fg-2">
          ScreenIQ ranks applicants against the criteria you set, shows the evidence behind every score, and gets your
          team from hundreds of resumes to a confident shortlist in minutes.
        </p>
        <div className="mt-9 flex flex-wrap justify-center gap-3">
          <ButtonLink to={primary.to} size="lg" className="h-12 px-6 text-base">{primary.label} <ArrowRight /></ButtonLink>
          <a href="#how" className="inline-flex h-12 items-center rounded-lg border border-line-strong bg-surface px-6 text-base font-medium text-fg shadow-card hover:bg-surface-3">
            See how it works
          </a>
        </div>
        <p className="mt-5 text-sm text-fg-3">Blind screening by default · Evidence for every score · Humans make the final call</p>

        {/* Product preview */}
        <div className="mx-auto mt-16 max-w-5xl rounded-[22px] border border-line bg-surface-3 p-2.5 text-left shadow-pop">
          <div className="flex overflow-hidden rounded-2xl border border-line bg-surface">
            <div className="hidden w-52 shrink-0 space-y-2.5 border-r border-line p-4 md:block" aria-hidden>
              {[0, 1, 2, 3, 4].map((i) => <div key={i} className={`h-9 rounded-lg ${i === 1 ? 'bg-brand-soft' : 'bg-surface-3'}`} />)}
            </div>
            <div className="min-w-0 flex-1 p-5 sm:p-7">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="text-xl font-semibold tracking-[-0.02em] text-fg">Senior Backend Engineer</div>
                  <div className="mt-1 text-sm text-fg-3">48 applicants · ranked by match score</div>
                </div>
                <span className="rounded-lg bg-brand px-3 py-1.5 text-sm font-semibold text-brand-fg">Share shortlist</span>
              </div>
              <ul className="mt-5 divide-y divide-line border-t border-line">
                {PREVIEW.map((p) => (
                  <li key={p.name} className="flex items-center gap-4 py-4">
                    <span className="flex size-10 shrink-0 items-center justify-center rounded-full bg-surface-3 text-xs font-semibold text-fg-2">{p.initials}</span>
                    <div className="w-40 shrink-0">
                      <div className="text-[15px] font-semibold text-fg">{p.name}</div>
                      <div className="text-[13px] text-fg-3">{p.role}</div>
                    </div>
                    <ScoreBar value={p.score} className="hidden sm:flex" />
                    <p className="hidden min-w-0 flex-1 text-sm text-fg-2 lg:block">{p.summary}</p>
                    <TierPill tier={p.tier} className="ml-auto" />
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
        <p className="mt-3 text-xs text-fg-3">Illustrative preview with sample candidates.</p>
      </section>

      {/* How it works */}
      <section id="how" className="mx-auto max-w-6xl scroll-mt-24 px-5 py-20">
        <p className="text-sm font-semibold uppercase tracking-wide text-brand-text">How it works</p>
        <h2 className="mt-3 max-w-xl text-4xl font-semibold leading-tight tracking-[-0.035em] text-fg sm:text-5xl">From job post to shortlist in three steps</h2>
        <div className="mt-12 grid gap-5 md:grid-cols-3">
          {STEPS.map((s) => (
            <div key={s.n} className="rounded-2xl border border-line bg-surface p-7 shadow-card">
              <div className="font-mono text-sm text-brand-text">{s.n}</div>
              <h3 className="mt-5 text-xl font-semibold tracking-[-0.015em] text-fg">{s.title}</h3>
              <p className="mt-3 text-[15px] leading-relaxed text-fg-2">{s.text}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Explainability */}
      <section id="receipts" className="scroll-mt-24 px-3 sm:px-5">
        <div className="mx-auto grid max-w-7xl gap-12 rounded-[28px] bg-[#18181b] px-7 py-16 text-[#f4f4f2] sm:px-14 lg:grid-cols-2 lg:items-center">
          <div>
            <p className="text-sm font-semibold uppercase tracking-wide text-[#b9baff]">No black boxes</p>
            <h2 className="mt-4 text-4xl font-semibold leading-[1.08] tracking-[-0.035em] sm:text-5xl">
              Every score comes with the <span className="font-serif font-normal italic text-[#b9baff]">receipts</span>
            </h2>
            <p className="mt-6 max-w-lg text-[17px] leading-relaxed text-white/70">
              See exactly which resume lines met each criterion, what’s missing, and what to ask in the interview. Scores ignore
              names, age and gender, quotes are verified against the resume, and every decision is logged for audits.
            </p>
            <ul className="mt-8 space-y-3.5 text-[15px]">
              {['Evidence linked to every criterion', 'Bias-reduced, blind scoring mode', 'Humans make the final call, always'].map((t) => (
                <li key={t} className="flex items-center gap-3"><Check className="size-4 text-[#b9baff]" />{t}</li>
              ))}
            </ul>
          </div>
          <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-6">
            <div className="flex items-center justify-between border-b border-white/10 pb-4">
              <span className="font-semibold">Criteria check · Ada Okafor</span>
              <span className="rounded-md bg-[#3d3fbd] px-2 py-0.5 text-sm font-semibold tabular">93</span>
            </div>
            <ul className="divide-y divide-white/10">
              {CRITERIA.map((c) => (
                <li key={c.name} className="flex items-start gap-3.5 py-4">
                  {c.ok ? (
                    <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-[#3d3fbd]"><Check className="size-3.5" strokeWidth={3} /></span>
                  ) : (
                    <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-[#de8434]/20 text-sm font-bold text-[#f0a765]">~</span>
                  )}
                  <div>
                    <div className="font-medium">{c.name}</div>
                    <div className="mt-0.5 text-sm text-white/55">{c.detail}</div>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </section>

      {/* Features */}
      <section id="features" className="mx-auto max-w-6xl scroll-mt-24 px-5 py-24">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-sm font-semibold uppercase tracking-wide text-brand-text">Features</p>
            <h2 className="mt-3 max-w-xl text-4xl font-semibold leading-tight tracking-[-0.035em] text-fg sm:text-5xl">Built for the way recruiters actually work</h2>
          </div>
          <p className="max-w-sm text-[17px] leading-relaxed text-fg-2">Everything your team needs to screen faster without losing the human judgement that makes a good hire.</p>
        </div>
        <div className="mt-12 grid overflow-hidden rounded-2xl border border-line bg-surface sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map(({ icon: Icon, title, text }) => (
            <div key={title} className="border-line p-8 [&:not(:last-child)]:border-b sm:[&:nth-child(odd)]:border-r lg:border-r lg:[&:nth-child(3n)]:border-r-0 lg:[&:nth-child(n+4)]:border-b-0">
              <div className="flex size-11 items-center justify-center rounded-xl bg-brand-soft"><Icon className="size-5 text-brand-text" /></div>
              <h3 className="mt-6 text-lg font-semibold text-fg">{title}</h3>
              <p className="mt-2 text-[15px] leading-relaxed text-fg-2">{text}</p>
            </div>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="mx-auto max-w-6xl px-5 pb-20">
        <div className="flex flex-col gap-8 rounded-[28px] bg-brand px-8 py-14 text-brand-fg sm:px-14 lg:flex-row lg:items-center lg:justify-between">
          <h2 className="max-w-xl text-4xl font-semibold leading-tight tracking-[-0.035em] sm:text-5xl">Your next great hire is already in your inbox.</h2>
          <div className="flex shrink-0 flex-wrap gap-3">
            <Link to={primary.to} className="inline-flex h-12 items-center gap-2 rounded-lg bg-white px-6 font-semibold text-brand hover:bg-white/90">{primary.label} <ArrowRight className="size-4" /></Link>
            {!me && <Link to="/login" className="inline-flex h-12 items-center rounded-lg border border-white/40 px-6 font-semibold text-white hover:bg-white/10">Log in</Link>}
          </div>
        </div>
      </section>

      <footer className="border-t border-line">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-3 px-5 py-8 text-sm text-fg-3 sm:flex-row">
          <Logo />
          <p>AI output is decision support. Hiring decisions remain with people.</p>
        </div>
      </footer>
    </div>
  )
}
