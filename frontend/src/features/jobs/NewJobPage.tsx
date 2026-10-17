import { useEffect, useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { ChevronLeft, Scale, Sparkles } from 'lucide-react'
import { api } from '@/lib/api'
import type { JDBiasReport } from '@/lib/types'
import { errorMessage } from '@/lib/utils'
import { PageHeader } from '@/components/layout/AppShell'
import { Card, CardBody, CardHeader } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Field, Input, Select, Textarea } from '@/components/ui/input'
import { Spinner } from '@/components/ui/misc'
import { useToast } from '@/components/ui/toast'
import { BiasReport } from './BiasReport'

const TEMPLATE = `About the role
Describe the team, the product and the impact of this role.

What you'll do:
-
-

Requirements:
- X+ years of professional experience
-

Nice to have:
- `

/** Debounced live call to the deterministic bias checker. */
function useLiveBiasReport(text: string) {
  const [report, setReport] = useState<JDBiasReport | null>(null)
  const [loading, setLoading] = useState(false)
  const enabled = text.trim().length >= 40
  useEffect(() => {
    if (!enabled) return
    const ctrl = new AbortController()
    const t = setTimeout(() => {
      setLoading(true)
      api.biasCheck(text, ctrl.signal).then(setReport).catch(() => {}).finally(() => setLoading(false))
    }, 450)
    return () => {
      clearTimeout(t)
      ctrl.abort()
    }
  }, [text, enabled])
  return { report: enabled ? report : null, loading: enabled && loading }
}

export function NewJobPage() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const [form, setForm] = useState({ title: '', department: '', location: '', employment_type: 'Full-time', description: '' })
  const { report, loading: checking } = useLiveBiasReport(form.description)

  const create = useMutation({
    mutationFn: () =>
      api.createJob({
        title: form.title.trim(),
        description: form.description.trim(),
        department: form.department.trim() || undefined,
        location: form.location.trim() || undefined,
        employment_type: form.employment_type || undefined,
      }),
    onSuccess: (job) => {
      qc.invalidateQueries({ queryKey: ['jobs'] })
      toast.success('Job created', 'AI is extracting requirements — you can upload resumes right away.')
      navigate(`/app/jobs/${job.id}`)
    },
    onError: (e) => toast.error('Couldn’t create job', errorMessage(e)),
  })

  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
    setForm({ ...form, [k]: e.target.value })
  const tooShort = form.description.trim().length < 50

  function submit(e: FormEvent) {
    e.preventDefault()
    if (!form.title.trim() || tooShort) return
    create.mutate()
  }

  return (
    <>
      <PageHeader
        breadcrumb={<Link to="/app/jobs" className="inline-flex items-center gap-1 hover:text-fg"><ChevronLeft className="size-4" />Jobs</Link>}
        title="Create a job"
        description="ScreenIQ extracts structured requirements from your description and scores every candidate against them."
      />
      <form onSubmit={submit} className="grid items-start gap-5 lg:grid-cols-[1fr_380px]">
        <Card>
          <CardBody className="space-y-5 pt-5">
            <Field label="Job title">
              {(id) => <Input id={id} required value={form.title} onChange={set('title')} placeholder="e.g. Senior Backend Engineer" />}
            </Field>
            <div className="grid gap-4 sm:grid-cols-3">
              <Field label="Department" optional>
                {(id) => <Input id={id} value={form.department} onChange={set('department')} placeholder="Engineering" />}
              </Field>
              <Field label="Location" optional>
                {(id) => <Input id={id} value={form.location} onChange={set('location')} placeholder="Remote" />}
              </Field>
              <Field label="Employment type">
                {(id) => (
                  <Select id={id} value={form.employment_type} onChange={set('employment_type')}>
                    {['Full-time', 'Part-time', 'Contract', 'Internship', 'Temporary'].map((t) => <option key={t}>{t}</option>)}
                  </Select>
                )}
              </Field>
            </div>
            <Field
              label="Job description"
              hint={tooShort ? 'At least 50 characters. Separate required and nice-to-have skills for the best results.' : `${form.description.trim().split(/\s+/).length} words`}
            >
              {(id) => (
                <div className="space-y-2">
                  <Textarea id={id} required value={form.description} onChange={set('description')} rows={18} className="font-mono text-[13px]" placeholder="Paste the full job description…" />
                  {!form.description && (
                    <button type="button" onClick={() => setForm({ ...form, description: TEMPLATE })} className="text-xs font-medium text-brand-text hover:underline">
                      Start from a template
                    </button>
                  )}
                </div>
              )}
            </Field>
          </CardBody>
          <div className="flex items-center justify-end gap-2 border-t border-line bg-surface-2 px-5 py-3.5">
            <Button variant="secondary" onClick={() => navigate('/app/jobs')}>Cancel</Button>
            <Button type="submit" loading={create.isPending} disabled={!form.title.trim() || tooShort}>
              <Sparkles /> Create & analyze
            </Button>
          </div>
        </Card>

        <Card className="lg:sticky lg:top-6">
          <CardHeader
            icon={<Scale />}
            title="Inclusive language check"
            description="Live analysis as you type"
            action={checking && <Spinner className="text-fg-3" />}
          />
          <CardBody>
            {report ? (
              <BiasReport report={report} compact />
            ) : (
              <p className="text-[13px] text-fg-3">
                Start writing the description to check for gender-coded, age-related, ableist or exclusionary wording.
                Inclusive job posts attract broader, more qualified applicant pools.
              </p>
            )}
          </CardBody>
        </Card>
      </form>
    </>
  )
}
