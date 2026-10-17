import { useState, type KeyboardEvent } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { X } from 'lucide-react'
import { api } from '@/lib/api'
import type { JobDetail } from '@/lib/types'
import { errorMessage } from '@/lib/utils'
import { Dialog } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Field, Input } from '@/components/ui/input'
import { useToast } from '@/components/ui/toast'
import { CriteriaChip } from '@/components/ui/tier'

function SkillListEditor({ label, hint, value, onChange, must }: {
  label: string
  hint: string
  value: string[]
  onChange: (v: string[]) => void
  must?: boolean
}) {
  const [draft, setDraft] = useState('')
  function add() {
    const items = draft.split(',').map((s) => s.trim()).filter(Boolean)
    const next = [...value]
    for (const it of items) if (!next.some((x) => x.toLowerCase() === it.toLowerCase())) next.push(it)
    onChange(next)
    setDraft('')
  }
  function onKey(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault()
      add()
    } else if (e.key === 'Backspace' && !draft && value.length) {
      onChange(value.slice(0, -1))
    }
  }
  return (
    <Field label={label} hint={hint}>
      {(id) => (
        <div className="rounded-lg border border-line-strong bg-surface p-2 focus-within:border-brand focus-within:ring-[3px] focus-within:ring-[var(--ring)]">
          <div className="flex flex-wrap gap-1.5">
            {value.map((s) => (
              <span key={s} className="inline-flex items-center">
                <CriteriaChip must={must}>
                  {s}
                  <button type="button" onClick={() => onChange(value.filter((x) => x !== s))} aria-label={`Remove ${s}`} className="-mr-0.5 ml-1 opacity-70 hover:opacity-100">
                    <X className="size-3" />
                  </button>
                </CriteriaChip>
              </span>
            ))}
            <input
              id={id}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={onKey}
              onBlur={() => draft.trim() && add()}
              placeholder={value.length ? 'Add another…' : 'Type a skill and press Enter'}
              className="min-w-32 flex-1 bg-transparent px-1 py-0.5 text-sm text-fg outline-none placeholder:text-fg-3"
            />
          </div>
        </div>
      )}
    </Field>
  )
}

export function CriteriaDialog({ job, open, onClose }: { job: JobDetail; open: boolean; onClose: () => void }) {
  const qc = useQueryClient()
  const toast = useToast()
  const x = job.extracted
  const [required, setRequired] = useState<string[]>(x?.required_skills ?? [])
  const [nice, setNice] = useState<string[]>(x?.nice_to_have_skills ?? [])
  const [years, setYears] = useState<string>(x?.min_years_experience ? String(x.min_years_experience) : '')

  const save = useMutation({
    mutationFn: () =>
      api.updateJob(job.id, {
        criteria: {
          required_skills: required,
          nice_to_have_skills: nice,
          min_years_experience: years.trim() ? Number(years) : null,
        },
      }),
    onSuccess: (j) => {
      qc.setQueryData(['job', job.id], j)
      qc.invalidateQueries({ queryKey: ['applications', job.id] })
      qc.invalidateQueries({ queryKey: ['jobs'] })
      toast.success('Criteria saved', `Re-scoring ${j.counts.total} candidate${j.counts.total === 1 ? '' : 's'} against the new criteria.`)
      onClose()
    },
    onError: (e) => toast.error('Couldn’t save criteria', errorMessage(e)),
  })

  const yearsInvalid = years.trim() !== '' && (Number.isNaN(Number(years)) || Number(years) < 0 || Number(years) > 40)

  return (
    <Dialog
      open={open}
      onClose={onClose}
      size="lg"
      title="Edit screening criteria"
      description="The AI drafted these from your job description. Must-haves weigh twice as much as nice-to-haves; saving re-scores every candidate."
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button onClick={() => save.mutate()} loading={save.isPending} disabled={!required.length || yearsInvalid}>Save & re-score</Button>
        </>
      }
    >
      <div className="space-y-5">
        <SkillListEditor label="Must-have skills" hint="Candidates missing these are pushed toward “Low fit”." value={required} onChange={setRequired} must />
        <SkillListEditor label="Nice to have" hint="Bonus points; never disqualifying." value={nice} onChange={setNice} />
        <Field label="Minimum years of experience" optional error={yearsInvalid ? 'Enter a number between 0 and 40' : null}>
          {(id) => <Input id={id} inputMode="decimal" value={years} onChange={(e) => setYears(e.target.value)} placeholder="e.g. 5" className="w-32" />}
        </Field>
      </div>
    </Dialog>
  )
}
