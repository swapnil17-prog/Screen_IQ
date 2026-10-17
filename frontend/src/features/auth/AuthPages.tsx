import { useState, type FormEvent, type ReactNode } from 'react'
import { Link, Navigate, useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { CheckCircle2, FileSearch, MailCheck, MessagesSquare, Scale } from 'lucide-react'
import { api } from '@/lib/api'
import { errorMessage } from '@/lib/utils'
import { useAuth } from '@/hooks/useAuth'
import { Button } from '@/components/ui/button'
import { Field, Input } from '@/components/ui/input'
import { PageLoader } from '@/components/ui/misc'
import { Logo } from '@/components/layout/Logo'

function AuthLayout({ title, subtitle, children, footer }: { title: string; subtitle: string; children: ReactNode; footer: ReactNode }) {
  return (
    <div className="grid min-h-screen lg:grid-cols-[1fr_1.05fr]">
      <div className="flex flex-col px-6 py-8 sm:px-12">
        <Link to="/" className="self-start"><Logo /></Link>
        <div className="mx-auto flex w-full max-w-sm flex-1 flex-col justify-center py-10">
          <h1 className="text-2xl font-semibold tracking-[-0.02em] text-fg">{title}</h1>
          <p className="mt-1.5 text-sm text-fg-2">{subtitle}</p>
          <div className="mt-8">{children}</div>
          <div className="mt-6 text-center text-sm text-fg-2">{footer}</div>
        </div>
      </div>
      <div className="relative hidden overflow-hidden border-l border-line bg-surface-2 lg:flex lg:flex-col lg:justify-center lg:px-14">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,var(--brand-soft),transparent_60%)]" aria-hidden />
        <div className="relative max-w-md">
          <p className="text-[13px] font-semibold uppercase tracking-wider text-brand-text">AI hiring, done responsibly</p>
          <h2 className="mt-3 text-3xl font-semibold leading-tight tracking-[-0.02em] text-fg">
            Screen faster. Interview smarter. Decide fairly.
          </h2>
          <ul className="mt-8 space-y-5">
            {[
              { icon: FileSearch, t: 'Evidence-backed scores', d: 'Every score cites the resume lines behind it — verified, not hallucinated.' },
              { icon: MessagesSquare, t: 'Gap-aware AI interviews', d: 'Structured interviews that probe exactly what the resume left unproven.' },
              { icon: Scale, t: 'Bias safeguards built in', d: 'Blind screening, inclusive-language checks and counterfactual audits.' },
            ].map(({ icon: Icon, t, d }) => (
              <li key={t} className="flex gap-3.5">
                <div className="flex size-9 shrink-0 items-center justify-center rounded-lg border border-line bg-surface shadow-card">
                  <Icon className="size-4 text-brand-text" />
                </div>
                <div>
                  <div className="text-sm font-semibold text-fg">{t}</div>
                  <div className="mt-0.5 text-sm text-fg-2">{d}</div>
                </div>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  )
}

export function LoginPage() {
  const { me, setSession } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const state = location.state as { from?: string; notice?: string } | null
  const from = state?.from ?? '/app'

  if (me) return <Navigate to={from} replace />

  async function submit(e: FormEvent) {
    e.preventDefault()
    setLoading(true)
    setError(null)
    try {
      setSession(await api.login(email, password))
      navigate(from, { replace: true })
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <AuthLayout
      title="Welcome back"
      subtitle="Sign in to your hiring workspace."
      footer={<>New to ScreenIQ? <Link to="/register" className="font-medium text-brand-text hover:underline">Create a workspace</Link></>}
    >
      <form onSubmit={submit} className="space-y-4" noValidate>
        {state?.notice && <p className="rounded-lg bg-good-soft px-3 py-2 text-sm text-good-text" role="status">{state.notice}</p>}
        <Field label="Work email">
          {(id) => <Input id={id} type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@company.com" />}
        </Field>
        <Field label={<span className="flex w-full items-center justify-between">Password<Link to="/forgot-password" className="font-normal text-brand-text hover:underline">Forgot password?</Link></span>}>
          {(id) => <Input id={id} type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} />}
        </Field>
        {error && <p className="rounded-lg bg-bad-soft px-3 py-2 text-sm text-bad-text" role="alert">{error}</p>}
        <Button type="submit" size="lg" className="w-full" loading={loading}>Sign in</Button>
      </form>
    </AuthLayout>
  )
}

export function RegisterPage() {
  const { me, setSession } = useAuth()
  const navigate = useNavigate()
  const { data: meta } = useQuery({ queryKey: ['meta'], queryFn: api.meta, staleTime: Infinity })
  const [form, setForm] = useState({ organization_name: '', full_name: '', email: '', password: '' })
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  if (me) return <Navigate to="/app" replace />

  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) => setForm({ ...form, [k]: e.target.value })
  const pwOk = form.password.length >= 8 && !/^[a-zA-Z]+$/.test(form.password) && !/^\d+$/.test(form.password)

  async function submit(e: FormEvent) {
    e.preventDefault()
    setLoading(true)
    setError(null)
    try {
      setSession(await api.register(form))
      navigate('/app', { replace: true })
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  if (meta && !meta.allow_public_signup) {
    return (
      <AuthLayout title="Sign-up is invite-only" subtitle="Ask a workspace administrator to add you." footer={<Link to="/login" className="font-medium text-brand-text hover:underline">Back to sign in</Link>}>
        <div />
      </AuthLayout>
    )
  }

  return (
    <AuthLayout
      title="Create your workspace"
      subtitle="Set up ScreenIQ for your hiring team in under a minute."
      footer={<>Already have an account? <Link to="/login" className="font-medium text-brand-text hover:underline">Sign in</Link></>}
    >
      <form onSubmit={submit} className="space-y-4">
        <Field label="Company or team name">
          {(id) => <Input id={id} required minLength={2} value={form.organization_name} onChange={set('organization_name')} placeholder="Acme Inc." />}
        </Field>
        <Field label="Your name">
          {(id) => <Input id={id} required autoComplete="name" value={form.full_name} onChange={set('full_name')} />}
        </Field>
        <Field label="Work email">
          {(id) => <Input id={id} type="email" required autoComplete="email" value={form.email} onChange={set('email')} placeholder="you@company.com" />}
        </Field>
        <Field
          label="Password"
          hint={
            <span className={pwOk ? 'inline-flex items-center gap-1 text-good-text' : ''}>
              {pwOk && <CheckCircle2 className="size-3.5" />}At least 8 characters, mixing letters with numbers or symbols.
            </span>
          }
        >
          {(id) => <Input id={id} type="password" required autoComplete="new-password" value={form.password} onChange={set('password')} />}
        </Field>
        {error && <p className="rounded-lg bg-bad-soft px-3 py-2 text-sm text-bad-text" role="alert">{error}</p>}
        <Button type="submit" size="lg" className="w-full" loading={loading}>Create workspace</Button>
      </form>
    </AuthLayout>
  )
}

const PASSWORD_HINT = 'At least 8 characters, mixing letters with numbers or symbols.'
const backToSignIn = <Link to="/login" className="font-medium text-brand-text hover:underline">Back to sign in</Link>

function ErrorNote({ error }: { error: string | null }) {
  return error ? <p className="rounded-lg bg-bad-soft px-3 py-2 text-sm text-bad-text" role="alert">{error}</p> : null
}

export function ForgotPasswordPage() {
  const [email, setEmail] = useState('')
  const [sent, setSent] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function submit(e: FormEvent) {
    e.preventDefault()
    setLoading(true)
    setError(null)
    try {
      await api.forgotPassword(email)
      setSent(true)
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  if (sent) {
    return (
      <AuthLayout title="Check your email" subtitle={`If an account exists for ${email}, we’ve sent it a link to reset the password.`} footer={backToSignIn}>
        <div className="flex items-start gap-3 rounded-xl border border-line bg-surface p-4 text-sm text-fg-2">
          <MailCheck className="mt-0.5 size-5 shrink-0 text-brand-text" />
          <p>The link works once and expires within an hour. Didn’t get it? Check your spam folder, or <button type="button" className="font-medium text-brand-text hover:underline" onClick={() => setSent(false)}>try again</button>.</p>
        </div>
      </AuthLayout>
    )
  }
  return (
    <AuthLayout title="Forgot your password?" subtitle="Enter your work email and we’ll send you a link to choose a new one." footer={backToSignIn}>
      <form onSubmit={submit} className="space-y-4">
        <Field label="Work email">
          {(id) => <Input id={id} type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@company.com" />}
        </Field>
        <ErrorNote error={error} />
        <Button type="submit" size="lg" className="w-full" loading={loading}>Send reset link</Button>
      </form>
    </AuthLayout>
  )
}

export function ResetPasswordPage() {
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const token = params.get('token') ?? ''
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function submit(e: FormEvent) {
    e.preventDefault()
    setLoading(true)
    setError(null)
    try {
      await api.resetPassword(token, password)
      navigate('/login', { replace: true, state: { notice: 'Your password has been updated. Sign in with your new password.' } })
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  if (!token) {
    return (
      <AuthLayout title="This link is incomplete" subtitle="Open the reset link from your email again, or request a new one." footer={backToSignIn}>
        <Link to="/forgot-password" className="text-sm font-medium text-brand-text hover:underline">Request a new reset link</Link>
      </AuthLayout>
    )
  }
  return (
    <AuthLayout title="Choose a new password" subtitle="You’ll use it to sign in to your workspace." footer={backToSignIn}>
      <form onSubmit={submit} className="space-y-4">
        <Field label="New password" hint={PASSWORD_HINT}>
          {(id) => <Input id={id} type="password" autoComplete="new-password" required minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} />}
        </Field>
        <ErrorNote error={error} />
        {error && <Link to="/forgot-password" className="block text-sm font-medium text-brand-text hover:underline">Request a new reset link</Link>}
        <Button type="submit" size="lg" className="w-full" loading={loading}>Update password</Button>
      </form>
    </AuthLayout>
  )
}

export function AcceptInvitePage() {
  const { setSession } = useAuth()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const token = params.get('token') ?? ''
  const { data: invite, error: inviteError, isLoading } = useQuery({
    queryKey: ['invitation', token],
    queryFn: () => api.invitation(token),
    enabled: !!token,
    retry: false,
  })
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function submit(e: FormEvent) {
    e.preventDefault()
    setLoading(true)
    setError(null)
    try {
      setSession(await api.acceptInvite(token, password))
      navigate('/app', { replace: true })
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  if (token && isLoading) return <PageLoader />
  if (!invite) {
    return (
      <AuthLayout title="This invitation isn’t valid" subtitle={inviteError ? errorMessage(inviteError) : 'Open the link from your invitation email again.'} footer={backToSignIn}>
        <p className="text-sm text-fg-2">Ask a workspace administrator to send you a new invitation.</p>
      </AuthLayout>
    )
  }
  return (
    <AuthLayout title={`Join ${invite.organization_name}`} subtitle={`Welcome, ${invite.full_name}. Choose a password to finish setting up your account.`} footer={backToSignIn}>
      <form onSubmit={submit} className="space-y-4">
        <Field label="Work email">{(id) => <Input id={id} type="email" value={invite.email} disabled readOnly />}</Field>
        <Field label="Password" hint={PASSWORD_HINT}>
          {(id) => <Input id={id} type="password" autoComplete="new-password" required minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} />}
        </Field>
        <ErrorNote error={error} />
        <Button type="submit" size="lg" className="w-full" loading={loading}>Accept invitation</Button>
      </form>
    </AuthLayout>
  )
}
