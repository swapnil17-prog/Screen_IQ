import { useState, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Building2, Cpu, History, KeyRound, SlidersHorizontal, UserPlus, Users } from 'lucide-react'
import { api } from '@/lib/api'
import type { OrganizationSettings } from '@/lib/types'
import { ACTION_LABELS, dateTime, timeAgo, titleCase } from '@/lib/format'
import { errorMessage } from '@/lib/utils'
import { useAuth, useSession } from '@/hooks/useAuth'
import { PageHeader } from '@/components/layout/AppShell'
import { Card, CardBody, CardHeader } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Field, Input, Select } from '@/components/ui/input'
import { Tabs } from '@/components/ui/tabs'
import { Avatar, PageLoader, Switch } from '@/components/ui/misc'
import { Dialog } from '@/components/ui/dialog'
import { useToast } from '@/components/ui/toast'
import { WeightsEditor } from '../jobs/WeightsEditor'

type Tab = 'workspace' | 'scoring' | 'team' | 'audit' | 'account' | 'system'

function useSaveOrg() {
  const qc = useQueryClient()
  const toast = useToast()
  return useMutation({
    mutationFn: api.updateOrganization,
    onSuccess: (org) => {
      qc.setQueryData(['me'], (old: { user: unknown } | null) => (old ? { ...old, organization: org } : old))
      toast.success('Settings saved')
    },
    onError: (e) => toast.error('Couldn’t save settings', errorMessage(e)),
  })
}

function Row({ title, description, children }: { title: string; description: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-3 py-4 sm:flex-row sm:items-center sm:justify-between">
      <div className="max-w-lg">
        <div className="text-sm font-medium text-fg">{title}</div>
        <div className="mt-0.5 text-[13px] text-fg-3">{description}</div>
      </div>
      <div className="shrink-0">{children}</div>
    </div>
  )
}

function WorkspaceTab() {
  const { organization } = useSession()
  const { can } = useAuth()
  const save = useSaveOrg()
  const [name, setName] = useState(organization.name)
  const [s, setS] = useState<OrganizationSettings>(organization.settings)
  const dirty = name !== organization.name || JSON.stringify(s) !== JSON.stringify(organization.settings)
  const disabled = !can('admin')
  const total = s.final_weights.screening + s.final_weights.interview || 1

  return (
    <Card className="max-w-3xl">
      <CardBody className="divide-y divide-line pt-2">
        <Row title="Workspace name" description="Shown to candidates in interview invitations.">
          <Input value={name} onChange={(e) => setName(e.target.value)} disabled={disabled} className="w-64" aria-label="Workspace name" />
        </Row>
        <Row title="Blind screening" description="Redact names, contact details, pronouns, age, family status, nationality, religion, institutions and locations before resume and interview text reaches the AI.">
          <Switch label="Blind screening" checked={s.blind_screening} disabled={disabled} onChange={(v) => setS({ ...s, blind_screening: v })} />
        </Row>
        <Row title="Bias-sensitivity threshold" description="Flag an evaluation for human review when the identity-visible and identity-masked grades differ by more than this many points.">
          <div className="flex items-center gap-2">
            <Input type="number" min={1} max={30} step={0.5} value={s.bias_delta_threshold} disabled={disabled}
              onChange={(e) => setS({ ...s, bias_delta_threshold: Number(e.target.value) })} className="w-20" aria-label="Bias threshold" />
            <span className="text-[13px] text-fg-3">points</span>
          </div>
        </Row>
        <Row title="Interview length" description="Number of AI-generated questions per interview.">
          <Select value={s.interview_question_count} disabled={disabled} onChange={(e) => setS({ ...s, interview_question_count: Number(e.target.value) })} className="w-28" aria-label="Question count">
            {[3, 4, 5, 6, 7, 8].map((n) => <option key={n} value={n}>{n} questions</option>)}
          </Select>
        </Row>
        <Row title="Follow-up questions" description="Maximum probing follow-ups the interviewer may ask per question when an answer is vague.">
          <Select value={s.interview_max_follow_ups} disabled={disabled} onChange={(e) => setS({ ...s, interview_max_follow_ups: Number(e.target.value) })} className="w-28" aria-label="Follow-ups">
            {[0, 1, 2, 3].map((n) => <option key={n} value={n}>{n}</option>)}
          </Select>
        </Row>
        <Row title="Invite on shortlist" description="When a candidate is shortlisted, generate their AI interview and email them a congratulations message with their private interview link.">
          <Switch label="Invite on shortlist" checked={s.auto_invite_on_shortlist} disabled={disabled} onChange={(v) => setS({ ...s, auto_invite_on_shortlist: v })} />
        </Row>
        <Row title="Final score blend" description={`Screening ${Math.round((s.final_weights.screening / total) * 100)}% · Interview ${Math.round((s.final_weights.interview / total) * 100)}%`}>
          <input type="range" min={0} max={1} step={0.05} value={s.final_weights.interview} disabled={disabled} aria-label="Interview weight"
            onChange={(e) => { const v = Number(e.target.value); setS({ ...s, final_weights: { interview: v, screening: Math.round((1 - v) * 100) / 100 } }) }}
            className="w-56 accent-[var(--brand)]" />
        </Row>
      </CardBody>
      {!disabled && (
        <div className="flex justify-end gap-2 border-t border-line bg-surface-2 px-5 py-3">
          <Button variant="secondary" disabled={!dirty} onClick={() => { setName(organization.name); setS(organization.settings) }}>Discard</Button>
          <Button disabled={!dirty} loading={save.isPending} onClick={() => save.mutate({ name, settings: s })}>Save changes</Button>
        </div>
      )}
    </Card>
  )
}

function ScoringTab() {
  const { organization } = useSession()
  const { can } = useAuth()
  const save = useSaveOrg()
  const [w, setW] = useState(organization.settings.scoring_weights)
  const dirty = JSON.stringify(w) !== JSON.stringify(organization.settings.scoring_weights)
  return (
    <Card className="max-w-3xl">
      <CardHeader title="Default screening weights" description="Applied to every job without custom weights. Changes affect new screenings; re-score a job to apply them to existing candidates." />
      <CardBody>
        <WeightsEditor value={w} onChange={setW} disabled={!can('admin')} />
        {can('admin') && (
          <div className="mt-6 border-t border-line pt-4">
            <Button disabled={!dirty} loading={save.isPending} onClick={() => save.mutate({ settings: { ...organization.settings, scoring_weights: w } })}>Save default weights</Button>
          </div>
        )}
      </CardBody>
    </Card>
  )
}

function TeamTab() {
  const { user: me } = useSession()
  const { can } = useAuth()
  const qc = useQueryClient()
  const toast = useToast()
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState({ email: '', full_name: '', role: 'recruiter', temporary_password: '' })
  const { data: users, isLoading } = useQuery({ queryKey: ['users'], queryFn: api.users })

  const invite = useMutation({
    mutationFn: () => api.inviteUser(form),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['users'] })
      toast.success('Teammate added', 'Share the temporary password with them securely.')
      setOpen(false)
      setForm({ email: '', full_name: '', role: 'recruiter', temporary_password: '' })
    },
    onError: (e) => toast.error('Couldn’t add teammate', errorMessage(e)),
  })
  const update = useMutation({
    mutationFn: ({ id, body }: { id: string; body: { role?: string; is_active?: boolean } }) => api.updateUser(id, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['users'] }),
    onError: (e) => toast.error('Couldn’t update teammate', errorMessage(e)),
  })

  function submit(e: FormEvent) {
    e.preventDefault()
    invite.mutate()
  }

  if (isLoading) return <PageLoader />
  return (
    <Card className="max-w-4xl">
      <CardHeader
        title="Team members"
        description="Owners and admins manage settings and the team; recruiters screen and interview; viewers have read-only access."
        action={can('admin') && <Button size="sm" onClick={() => setOpen(true)}><UserPlus /> Add teammate</Button>}
      />
      <ul className="divide-y divide-line border-t border-line">
        {users?.map((u) => (
          <li key={u.id} className="flex flex-wrap items-center gap-3 px-5 py-3">
            <Avatar name={u.full_name} size="sm" />
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2 text-sm font-medium text-fg">{u.full_name}{u.id === me.id && <Badge>You</Badge>}{!u.is_active && <Badge tone="bad">Deactivated</Badge>}</div>
              <div className="text-xs text-fg-3">{u.email} · last active {timeAgo(u.last_login_at)}</div>
            </div>
            {can('admin') && u.role !== 'owner' && u.id !== me.id ? (
              <div className="flex items-center gap-2">
                <Select value={u.role} onChange={(e) => update.mutate({ id: u.id, body: { role: e.target.value } })} className="h-8 w-32 text-[13px]" aria-label={`Role for ${u.full_name}`}>
                  {['admin', 'recruiter', 'viewer'].map((r) => <option key={r} value={r}>{titleCase(r)}</option>)}
                </Select>
                <Button variant="ghost" size="sm" onClick={() => update.mutate({ id: u.id, body: { is_active: !u.is_active } })}>
                  {u.is_active ? 'Deactivate' : 'Reactivate'}
                </Button>
              </div>
            ) : <Badge tone={u.role === 'owner' ? 'brand' : 'neutral'}>{titleCase(u.role)}</Badge>}
          </li>
        ))}
      </ul>
      <Dialog
        open={open}
        onClose={() => setOpen(false)}
        title="Add a teammate"
        description="They sign in with this email and the temporary password, then change it under Account."
        footer={<><Button variant="secondary" onClick={() => setOpen(false)}>Cancel</Button><Button type="submit" form="invite-form" loading={invite.isPending}>Add teammate</Button></>}
      >
        <form id="invite-form" onSubmit={submit} className="space-y-4">
          <Field label="Full name">{(id) => <Input id={id} required value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} />}</Field>
          <Field label="Email">{(id) => <Input id={id} type="email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />}</Field>
          <Field label="Role">{(id) => (
            <Select id={id} value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
              <option value="admin">Admin</option><option value="recruiter">Recruiter</option><option value="viewer">Viewer</option>
            </Select>
          )}</Field>
          <Field label="Temporary password" hint="8+ characters, mixing letters with numbers or symbols.">
            {(id) => <Input id={id} type="text" required minLength={8} autoComplete="off" value={form.temporary_password} onChange={(e) => setForm({ ...form, temporary_password: e.target.value })} />}
          </Field>
        </form>
      </Dialog>
    </Card>
  )
}

function AuditTab() {
  const [offset, setOffset] = useState(0)
  const { data, isLoading } = useQuery({ queryKey: ['audit', offset], queryFn: () => api.auditLogs({ limit: 50, offset }) })
  if (isLoading || !data) return <PageLoader />
  return (
    <Card>
      <CardHeader title="Audit log" description="Append-only record of every hiring action — who, what, when, and from where." />
      <div className="overflow-x-auto border-t border-line">
        <table className="w-full text-left text-[13px]">
          <thead>
            <tr className="text-[11px] uppercase tracking-wide text-fg-3">
              <th className="py-2 pl-5 pr-4 font-medium">When</th><th className="py-2 pr-4 font-medium">Actor</th><th className="py-2 pr-4 font-medium">Action</th><th className="hidden py-2 pr-5 font-medium md:table-cell">Details</th>
            </tr>
          </thead>
          <tbody>
            {data.items.map((a) => (
              <tr key={a.id} className="border-t border-line align-top">
                <td className="whitespace-nowrap py-2.5 pl-5 pr-4 text-fg-3">{dateTime(a.created_at)}</td>
                <td className="py-2.5 pr-4 text-fg">{a.actor_type === 'user' ? a.actor_name ?? 'User' : titleCase(a.actor_type)}</td>
                <td className="py-2.5 pr-4 text-fg-2"><code className="font-mono text-xs text-fg">{a.action}</code><div className="text-xs text-fg-3">{ACTION_LABELS[a.action]}</div></td>
                <td className="hidden max-w-md truncate py-2.5 pr-5 font-mono text-xs text-fg-3 md:table-cell" title={JSON.stringify(a.details)}>
                  {Object.keys(a.details).length ? JSON.stringify(a.details) : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="flex items-center justify-between border-t border-line px-5 py-3 text-[13px] text-fg-3">
        <span>{data.total} events</span>
        <div className="flex gap-2">
          <Button variant="secondary" size="sm" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 50))}>Newer</Button>
          <Button variant="secondary" size="sm" disabled={offset + 50 >= data.total} onClick={() => setOffset(offset + 50)}>Older</Button>
        </div>
      </div>
    </Card>
  )
}

function AccountTab() {
  const { user } = useSession()
  const toast = useToast()
  const [cur, setCur] = useState('')
  const [next, setNext] = useState('')
  const change = useMutation({
    mutationFn: () => api.changePassword(cur, next),
    onSuccess: () => { toast.success('Password changed'); setCur(''); setNext('') },
    onError: (e) => toast.error('Couldn’t change password', errorMessage(e)),
  })
  return (
    <div className="max-w-xl space-y-4">
      <Card>
        <CardBody className="flex items-center gap-4 pt-5">
          <Avatar name={user.full_name} size="lg" />
          <div>
            <div className="text-base font-semibold text-fg">{user.full_name}</div>
            <div className="text-sm text-fg-2">{user.email}</div>
            <Badge className="mt-1.5" tone="brand">{titleCase(user.role)}</Badge>
          </div>
        </CardBody>
      </Card>
      <Card>
        <CardHeader icon={<KeyRound />} title="Change password" />
        <CardBody>
          <form onSubmit={(e) => { e.preventDefault(); change.mutate() }} className="space-y-4">
            <Field label="Current password">{(id) => <Input id={id} type="password" autoComplete="current-password" value={cur} onChange={(e) => setCur(e.target.value)} required />}</Field>
            <Field label="New password" hint="8+ characters, mixing letters with numbers or symbols.">{(id) => <Input id={id} type="password" autoComplete="new-password" value={next} onChange={(e) => setNext(e.target.value)} required minLength={8} />}</Field>
            <Button type="submit" loading={change.isPending} disabled={!cur || next.length < 8}>Update password</Button>
          </form>
        </CardBody>
      </Card>
    </div>
  )
}

function SystemTab() {
  const { data } = useQuery({ queryKey: ['meta'], queryFn: api.meta, staleTime: Infinity })
  if (!data) return <PageLoader />
  const rows: [string, string][] = [
    ['Version', data.version],
    ['Environment', data.environment],
    ['LLM provider', data.llm_provider === 'mock' ? 'Offline mock (demo)' : 'Anthropic Claude'],
    ['LLM model', data.llm_model],
    ['Embeddings', { bge: 'BGE-large (local)', openai: 'OpenAI text-embedding-3-small', hash: 'Lexical hashing (demo)' }[data.embedding_provider]],
    ['Email delivery', data.email_delivery === 'smtp' ? 'SMTP' : 'Not configured (logged to server console)'],
    ['Upload limit', `${data.max_upload_mb} MB · ${data.max_files_per_upload} files per batch`],
  ]
  return (
    <Card className="max-w-xl">
      <CardHeader icon={<Cpu />} title="System" description="Deployment configuration (read-only)" />
      <dl className="divide-y divide-line border-t border-line text-sm">
        {rows.map(([k, v]) => (
          <div key={k} className="flex justify-between gap-4 px-5 py-2.5"><dt className="text-fg-3">{k}</dt><dd className="text-right font-medium text-fg">{v}</dd></div>
        ))}
      </dl>
    </Card>
  )
}

export function SettingsPage() {
  const { can } = useAuth()
  const [tab, setTab] = useState<Tab>('workspace')
  const { organization } = useSession()
  // Remount the forms when the saved organization changes, resetting their local drafts
  const orgKey = JSON.stringify(organization)
  const items = [
    { key: 'workspace' as const, label: 'Workspace', icon: <Building2 /> },
    { key: 'scoring' as const, label: 'Scoring', icon: <SlidersHorizontal /> },
    { key: 'team' as const, label: 'Team', icon: <Users /> },
    ...(can('admin') ? [{ key: 'audit' as const, label: 'Audit log', icon: <History /> }] : []),
    { key: 'account' as const, label: 'Account', icon: <KeyRound /> },
    { key: 'system' as const, label: 'System', icon: <Cpu /> },
  ]
  return (
    <>
      <PageHeader title="Settings" description="Configure your workspace, fairness safeguards, scoring and team." />
      <Tabs className="mb-6" items={items} value={tab} onChange={setTab} />
      {tab === 'workspace' && <WorkspaceTab key={orgKey} />}
      {tab === 'scoring' && <ScoringTab key={orgKey} />}
      {tab === 'team' && <TeamTab />}
      {tab === 'audit' && <AuditTab />}
      {tab === 'account' && <AccountTab />}
      {tab === 'system' && <SystemTab />}
    </>
  )
}
