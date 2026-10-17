import { useEffect, useRef, useState, type ReactNode } from 'react'
import { NavLink, Navigate, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  Bell,
  Briefcase,
  ChevronsUpDown,
  Cpu,
  FlaskConical,
  LayoutDashboard,
  LogOut,
  Menu as MenuIcon,
  MessagesSquare,
  Monitor,
  Moon,
  Scale,
  Search,
  Settings,
  Sun,
  Upload,
  Users,
  X,
} from 'lucide-react'
import { useAuth } from '@/hooks/useAuth'
import { useTheme, type ThemePref } from '@/hooks/useTheme'
import { api } from '@/lib/api'
import { ACTION_LABELS, titleCase, timeAgo } from '@/lib/format'
import { cn } from '@/lib/utils'
import { Avatar, Kbd, PageLoader } from '@/components/ui/misc'
import { Menu, MenuItem, MenuLabel } from '@/components/ui/menu'
import { Button } from '@/components/ui/button'
import { UploadDialog } from '@/features/jobs/UploadDialog'
import { Logo } from './Logo'

export function RequireAuth() {
  const { me, loading } = useAuth()
  const location = useLocation()
  if (loading) return <PageLoader label="Loading your workspace…" />
  if (!me) return <Navigate to="/login" replace state={{ from: location.pathname }} />
  return <AppShell />
}

function NavItem({
  to,
  label,
  icon: Icon,
  end,
  count,
  onNavigate,
}: {
  to: string
  label: string
  icon: typeof LayoutDashboard
  end?: boolean
  count?: number
  onNavigate?: () => void
}) {
  return (
    <NavLink
      to={to}
      end={end}
      onClick={onNavigate}
      className={({ isActive }) =>
        cn(
          'flex items-center gap-3 rounded-lg px-3 py-2 text-[14px] font-medium transition-colors',
          isActive ? 'bg-brand-soft text-brand-text' : 'text-fg-2 hover:bg-surface-3 hover:text-fg',
        )
      }
    >
      <Icon className="size-[18px] shrink-0" />
      <span className="flex-1">{label}</span>
      {count !== undefined && count > 0 && <span className="text-xs text-fg-3 tabular">{count}</span>}
    </NavLink>
  )
}

const THEMES: { key: ThemePref; label: string; icon: ReactNode }[] = [
  { key: 'light', label: 'Light', icon: <Sun /> },
  { key: 'dark', label: 'Dark', icon: <Moon /> },
  { key: 'system', label: 'System', icon: <Monitor /> },
]

function EngineCard() {
  const { data } = useQuery({ queryKey: ['meta'], queryFn: api.meta, staleTime: Infinity })
  if (!data) return null
  const mock = data.llm_provider === 'mock'
  return (
    <div className="rounded-xl border border-line bg-surface-2 p-3.5">
      <div className="flex items-center gap-2 text-[13px] font-semibold text-fg">
        {mock ? <FlaskConical className="size-4 text-warn-text" /> : <Cpu className="size-4 text-brand-text" />}
        {mock ? 'Demo AI engine' : 'AI engine'}
      </div>
      <p className="mt-1 text-xs text-fg-3">
        {mock ? 'Simulated output — connect Claude for real analysis.' : `${data.llm_model} · ${data.embedding_provider} embeddings`}
      </p>
    </div>
  )
}

function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const { me, logout } = useAuth()
  const { theme, setTheme } = useTheme()
  const navigate = useNavigate()
  const { data: jobs } = useQuery({ queryKey: ['jobs', 'open'], queryFn: () => api.jobs({ status: 'open' }), enabled: !!me })
  if (!me) return null

  return (
    <div className="flex h-full flex-col px-4 py-5">
      <div className="px-2 pb-6"><Logo /></div>
      <nav className="flex flex-col gap-1" aria-label="Main">
        <NavItem to="/app" end label="Dashboard" icon={LayoutDashboard} onNavigate={onNavigate} />
        <NavItem to="/app/jobs" label="Jobs" icon={Briefcase} count={jobs?.length} onNavigate={onNavigate} />
        <NavItem to="/app/candidates" label="Candidates" icon={Users} onNavigate={onNavigate} />
        <NavItem to="/app/interviews" label="Interviews" icon={MessagesSquare} onNavigate={onNavigate} />
        <NavItem to="/app/fairness" label="Fairness" icon={Scale} onNavigate={onNavigate} />
        <NavItem to="/app/settings" label="Settings" icon={Settings} onNavigate={onNavigate} />
      </nav>

      <div className="mt-auto space-y-3">
        <EngineCard />
        <Menu
          align="start"
          className="bottom-full mb-1.5 w-60"
          trigger={({ toggle }) => (
            <button onClick={toggle} className="flex w-full items-center gap-3 rounded-xl p-2 text-left transition-colors hover:bg-surface-3">
              <Avatar name={me.user.full_name} />
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm font-semibold text-fg">{me.user.full_name}</div>
                <div className="truncate text-xs text-fg-3">{titleCase(me.user.role)} · {me.organization.name}</div>
              </div>
              <ChevronsUpDown className="size-4 text-fg-3" />
            </button>
          )}
        >
          {(close) => (
            <>
              <MenuLabel>Theme</MenuLabel>
              <div className="grid grid-cols-3 gap-1 px-1 pb-1">
                {THEMES.map((t) => (
                  <button
                    key={t.key}
                    onClick={() => setTheme(t.key)}
                    aria-pressed={theme === t.key}
                    className={cn(
                      'flex flex-col items-center gap-1 rounded-lg py-1.5 text-[11px] transition-colors [&_svg]:size-4',
                      theme === t.key ? 'bg-brand-soft text-brand-text' : 'text-fg-2 hover:bg-surface-3',
                    )}
                  >
                    {t.icon}
                    {t.label}
                  </button>
                ))}
              </div>
              <div className="my-1 h-px bg-line" />
              <MenuItem icon={<Settings />} onClick={() => { close(); navigate('/app/settings'); onNavigate?.() }}>Settings</MenuItem>
              <MenuItem icon={<LogOut />} onClick={async () => { close(); await logout(); navigate('/login') }}>Sign out</MenuItem>
            </>
          )}
        </Menu>
      </div>
    </div>
  )
}

function GlobalSearch() {
  const navigate = useNavigate()
  const [q, setQ] = useState('')
  const input = useRef<HTMLInputElement>(null)

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        input.current?.focus()
      }
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [])

  return (
    <form
      role="search"
      onSubmit={(e) => {
        e.preventDefault()
        if (q.trim()) navigate(`/app/candidates?q=${encodeURIComponent(q.trim())}`)
      }}
      className="relative w-full max-w-md"
    >
      <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-fg-3" />
      <input
        ref={input}
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="Search candidates, skills, or jobs"
        aria-label="Search candidates"
        className="h-10 w-full rounded-lg border border-line bg-surface-3/60 pl-9 pr-14 text-sm text-fg outline-none transition placeholder:text-fg-3 focus:border-brand focus:bg-surface focus:ring-[3px] focus:ring-[var(--ring)]"
      />
      <span className="absolute right-2.5 top-1/2 -translate-y-1/2"><Kbd>⌘K</Kbd></span>
    </form>
  )
}

function ActivityBell() {
  const { data } = useQuery({ queryKey: ['dashboard', 7], queryFn: () => api.dashboard(7), refetchInterval: 60_000 })
  const items = data?.recent_activity ?? []
  return (
    <Menu
      className="w-80"
      trigger={({ toggle }) => (
        <Button variant="ghost" size="icon" onClick={toggle} aria-label="Recent activity" className="relative">
          <Bell />
          {items.length > 0 && <span className="absolute right-2 top-2 size-1.5 rounded-full bg-brand" />}
        </Button>
      )}
    >
      {() => (
        <div className="max-h-96 overflow-y-auto">
          <MenuLabel>Recent activity</MenuLabel>
          {items.length === 0 && <p className="px-2.5 py-3 text-sm text-fg-3">Nothing yet.</p>}
          {items.map((a) => (
            <div key={a.id} className="rounded-lg px-2.5 py-2 text-[13px]">
              <p className="text-fg-2">
                <span className="font-medium text-fg">
                  {a.actor_type === 'system' ? 'ScreenIQ' : a.actor_type === 'candidate' ? 'A candidate' : a.actor_name ?? 'Someone'}
                </span>{' '}
                {ACTION_LABELS[a.action] ?? a.action}
              </p>
              <p className="text-xs text-fg-3">{timeAgo(a.created_at)}</p>
            </div>
          ))}
        </div>
      )}
    </Menu>
  )
}

function DemoBanner() {
  const { data } = useQuery({ queryKey: ['meta'], queryFn: api.meta, staleTime: Infinity })
  if (!data || data.llm_provider !== 'mock') return null
  return (
    <div className="flex items-center justify-center gap-2 border-b border-line bg-warn-soft px-4 py-1.5 text-center text-xs text-warn-text">
      <FlaskConical className="size-3.5 shrink-0" />
      <span>
        <strong className="font-semibold">Demo mode:</strong> AI output is simulated by the offline heuristic model.
        Set <code className="font-mono">LLM_PROVIDER=anthropic</code> for real Claude analysis.
      </span>
    </div>
  )
}

export function AppShell() {
  const { can } = useAuth()
  const [mobileOpen, setMobileOpen] = useState(false)
  const [uploadOpen, setUploadOpen] = useState(false)

  return (
    <div className="flex min-h-screen">
      <aside className="sticky top-0 hidden h-screen w-64 shrink-0 border-r border-line bg-surface lg:block">
        <Sidebar />
      </aside>

      {mobileOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 animate-fade-in bg-black/40" onClick={() => setMobileOpen(false)} />
          <aside className="relative h-full w-72 animate-slide-up border-r border-line bg-surface">
            <Button variant="ghost" size="icon-sm" className="absolute right-3 top-4" onClick={() => setMobileOpen(false)} aria-label="Close menu">
              <X />
            </Button>
            <Sidebar onNavigate={() => setMobileOpen(false)} />
          </aside>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <DemoBanner />
        <header className="sticky top-0 z-30 flex h-16 items-center gap-3 border-b border-line bg-page/85 px-4 backdrop-blur sm:px-6 lg:px-8">
          <Button variant="ghost" size="icon-sm" onClick={() => setMobileOpen(true)} aria-label="Open menu" className="lg:hidden">
            <MenuIcon />
          </Button>
          <div className="hidden flex-1 sm:block"><GlobalSearch /></div>
          <div className="flex-1 sm:hidden"><Logo /></div>
          <ActivityBell />
          {can('write') && (
            <Button onClick={() => setUploadOpen(true)}>
              <Upload /> <span className="hidden sm:inline">Upload resumes</span>
            </Button>
          )}
        </header>
        <main className="mx-auto w-full max-w-[1320px] flex-1 px-4 py-7 sm:px-6 lg:px-8">
          <Outlet />
        </main>
      </div>
      <UploadDialog open={uploadOpen} onClose={() => setUploadOpen(false)} />
    </div>
  )
}

export function PageHeader({
  title,
  description,
  actions,
  breadcrumb,
}: {
  title: ReactNode
  description?: ReactNode
  actions?: ReactNode
  breadcrumb?: ReactNode
}) {
  return (
    <div className="mb-7 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div className="min-w-0">
        {breadcrumb && <div className="mb-2 text-[13px] text-fg-3">{breadcrumb}</div>}
        <h1 className="text-[26px] font-semibold tracking-[-0.025em] text-fg">{title}</h1>
        {description && <div className="mt-1 text-[15px] text-fg-2">{description}</div>}
      </div>
      {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
    </div>
  )
}
