import { useCallback, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CheckCircle2, CircleAlert, Copy, FileText, UploadCloud, X } from 'lucide-react'
import { api } from '@/lib/api'
import type { UploadResult } from '@/lib/types'
import { cn, errorMessage } from '@/lib/utils'
import { Dialog } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Field, Select } from '@/components/ui/input'
import { useToast } from '@/components/ui/toast'

const ACCEPT = ['.pdf', '.docx', '.txt']

function sizeLabel(bytes: number) {
  return bytes < 1024 * 1024 ? `${Math.max(1, Math.round(bytes / 1024))} KB` : `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

/** Pass `jobId` to upload into a known job; omit it to let the user pick an open job. */
export function UploadDialog({ jobId, open, onClose }: { jobId?: string; open: boolean; onClose: () => void }) {
  const qc = useQueryClient()
  const toast = useToast()
  const navigate = useNavigate()
  const { data: meta } = useQuery({ queryKey: ['meta'], queryFn: api.meta, staleTime: Infinity })
  const { data: jobs } = useQuery({ queryKey: ['jobs', 'open'], queryFn: () => api.jobs({ status: 'open' }), enabled: open && !jobId })
  const [pickedJob, setPickedJob] = useState('')
  const targetJob = jobId ?? pickedJob
  const maxMb = meta?.max_upload_mb ?? 10
  const maxFiles = meta?.max_files_per_upload ?? 25
  const [files, setFiles] = useState<File[]>([])
  const [rejected, setRejected] = useState<string[]>([])
  const [drag, setDrag] = useState(false)
  const [result, setResult] = useState<UploadResult | null>(null)
  const input = useRef<HTMLInputElement>(null)

  const add = useCallback(
    (list: FileList | File[]) => {
      const next: File[] = []
      const bad: string[] = []
      for (const f of Array.from(list)) {
        const ext = f.name.slice(f.name.lastIndexOf('.')).toLowerCase()
        if (!ACCEPT.includes(ext)) bad.push(`${f.name}: unsupported type (use PDF, DOCX or TXT)`)
        else if (f.size > maxMb * 1024 * 1024) bad.push(`${f.name}: larger than ${maxMb} MB`)
        else next.push(f)
      }
      setFiles((cur) => {
        const merged = [...cur]
        for (const f of next) if (!merged.some((m) => m.name === f.name && m.size === f.size)) merged.push(f)
        return merged.slice(0, maxFiles)
      })
      setRejected(bad)
    },
    [maxMb, maxFiles],
  )

  const upload = useMutation({
    mutationFn: () => api.uploadResumes(targetJob, files),
    onSuccess: (res) => {
      setResult(res)
      qc.invalidateQueries({ queryKey: ['applications', targetJob] })
      qc.invalidateQueries({ queryKey: ['job', targetJob] })
      qc.invalidateQueries({ queryKey: ['jobs'] })
      if (res.created.length) toast.success(`${res.created.length} resume${res.created.length > 1 ? 's' : ''} queued for screening`)
    },
    onError: (e) => toast.error('Upload failed', errorMessage(e)),
  })

  function close() {
    setFiles([])
    setRejected([])
    setResult(null)
    setPickedJob('')
    onClose()
  }

  return (
    <Dialog
      open={open}
      onClose={close}
      size="lg"
      title="Upload resumes"
      description="Each resume is parsed, analyzed and scored against this job automatically."
      footer={
        result ? (
          <>
            {!jobId && <Button variant="secondary" onClick={() => { const id = targetJob; close(); navigate(`/app/jobs/${id}`) }}>View ranked list</Button>}
            <Button onClick={close}>Done</Button>
          </>
        ) : (
          <>
            <Button variant="secondary" onClick={close}>Cancel</Button>
            <Button onClick={() => upload.mutate()} disabled={!files.length || !targetJob} loading={upload.isPending}>
              <UploadCloud /> Upload {files.length > 0 && `${files.length} file${files.length > 1 ? 's' : ''}`}
            </Button>
          </>
        )
      }
    >
      {result ? (
        <div className="space-y-3">
          {result.created.length > 0 && (
            <div className="flex items-start gap-2.5 rounded-lg bg-good-soft p-3 text-sm text-good-text">
              <CheckCircle2 className="mt-0.5 size-4 shrink-0" />
              <span><strong>{result.created.length}</strong> candidate{result.created.length > 1 ? 's are' : ' is'} being screened. Scores appear in the table within moments.</span>
            </div>
          )}
          {result.duplicates.length > 0 && (
            <div className="flex items-start gap-2.5 rounded-lg bg-surface-3 p-3 text-sm text-fg-2">
              <Copy className="mt-0.5 size-4 shrink-0" />
              <span>{result.duplicates.length} already in this job: {result.duplicates.map((d) => d.candidate.full_name ?? 'candidate').join(', ')}</span>
            </div>
          )}
          {result.errors.map((e) => (
            <div key={e.filename} className="flex items-start gap-2.5 rounded-lg bg-bad-soft p-3 text-sm text-bad-text">
              <CircleAlert className="mt-0.5 size-4 shrink-0" />
              <span><strong>{e.filename}</strong> — {e.message}</span>
            </div>
          ))}
        </div>
      ) : (
        <div className="space-y-4">
          {!jobId && (
            <Field label="Job">
              {(id) => (
                <Select id={id} value={pickedJob} onChange={(e) => setPickedJob(e.target.value)}>
                  <option value="">{jobs?.length === 0 ? 'No open jobs — create one first' : 'Select the job these resumes are for…'}</option>
                  {jobs?.map((j) => <option key={j.id} value={j.id}>{j.title}</option>)}
                </Select>
              )}
            </Field>
          )}
          <button
            type="button"
            onClick={() => input.current?.click()}
            onDragOver={(e) => { e.preventDefault(); setDrag(true) }}
            onDragLeave={() => setDrag(false)}
            onDrop={(e) => { e.preventDefault(); setDrag(false); add(e.dataTransfer.files) }}
            className={cn(
              'flex w-full flex-col items-center justify-center rounded-xl border-2 border-dashed px-6 py-10 text-center transition-colors',
              drag ? 'border-brand bg-brand-soft' : 'border-line-strong bg-surface-2 hover:border-brand hover:bg-brand-soft/50',
            )}
          >
            <div className="flex size-11 items-center justify-center rounded-full bg-surface shadow-card">
              <UploadCloud className="size-5 text-brand-text" />
            </div>
            <p className="mt-3 text-sm font-medium text-fg">Drop resumes here or <span className="text-brand-text">browse</span></p>
            <p className="mt-1 text-xs text-fg-3">PDF, DOCX or TXT · up to {maxMb} MB each · {maxFiles} files per batch</p>
          </button>
          <input ref={input} type="file" multiple accept={ACCEPT.join(',')} className="sr-only" onChange={(e) => { if (e.target.files) add(e.target.files); e.target.value = '' }} />

          {rejected.map((r) => <p key={r} className="text-xs text-bad-text">{r}</p>)}

          {files.length > 0 && (
            <ul className="max-h-56 divide-y divide-line overflow-y-auto rounded-lg border border-line">
              {files.map((f) => (
                <li key={f.name + f.size} className="flex items-center gap-3 px-3 py-2">
                  <FileText className="size-4 shrink-0 text-fg-3" />
                  <span className="min-w-0 flex-1 truncate text-sm text-fg">{f.name}</span>
                  <span className="text-xs text-fg-3 tabular">{sizeLabel(f.size)}</span>
                  <button onClick={() => setFiles(files.filter((x) => x !== f))} className="text-fg-3 hover:text-fg" aria-label={`Remove ${f.name}`}>
                    <X className="size-4" />
                  </button>
                </li>
              ))}
            </ul>
          )}
          <p className="text-xs text-fg-3">
            Resumes are processed with blind screening when enabled: names, contact details and demographic signals are redacted before AI assessment.
          </p>
        </div>
      )}
    </Dialog>
  )
}
