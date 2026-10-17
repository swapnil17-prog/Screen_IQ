import { useState } from 'react'
import { GraduationCap } from 'lucide-react'
import type { ResumeExtraction } from '@/lib/types'
import { Card, CardBody } from '@/components/ui/card'
import { Chip } from '@/components/ui/badge'
import { Segmented } from '@/components/ui/tabs'

export function ResumePanel({ profile, skills, rawText }: { profile: ResumeExtraction | null; skills: string[]; rawText?: string }) {
  const [view, setView] = useState<'parsed' | 'raw'>('parsed')
  return (
    <Card>
      <div className="flex items-center justify-between border-b border-line px-5 py-3.5">
        <div>
          <h3 className="text-[14px] font-semibold text-fg">Resume</h3>
          <p className="text-[13px] text-fg-3">Structured by the parser & skill extractor</p>
        </div>
        {rawText !== undefined && (
          <Segmented value={view} onChange={setView} items={[{ key: 'parsed', label: 'Parsed' }, { key: 'raw', label: 'Raw text' }]} />
        )}
      </div>
      {view === 'raw' && rawText !== undefined ? (
        <CardBody className="pt-4">
          <pre className="max-h-[70vh] overflow-auto whitespace-pre-wrap font-sans text-[13px] leading-relaxed text-fg-2">{rawText}</pre>
        </CardBody>
      ) : !profile ? (
        <CardBody className="pt-4 text-sm text-fg-3">Not parsed yet.</CardBody>
      ) : (
        <div className="space-y-6 px-5 py-5">
          {profile.summary && <p className="text-sm leading-relaxed text-fg-2">{profile.summary}</p>}
          <section>
            <h4 className="mb-3 text-xs font-semibold uppercase tracking-wide text-fg-3">Experience</h4>
            <div className="space-y-4">
              {profile.work_history.map((w, i) => (
                <div key={`${w.company}-${i}`}>
                  <div className="flex flex-wrap items-baseline justify-between gap-2">
                    <div className="text-sm font-semibold text-fg">{w.title} <span className="font-normal text-fg-2">· {w.company}</span></div>
                    <div className="text-xs text-fg-3">{[w.start_date, w.end_date ?? 'present'].filter(Boolean).join(' – ')}</div>
                  </div>
                  <ul className="mt-1.5 space-y-1">
                    {w.highlights.map((h) => <li key={h} className="flex gap-2 text-[13px] text-fg-2"><span className="mt-[7px] size-1 shrink-0 rounded-full bg-fg-3" />{h}</li>)}
                  </ul>
                </div>
              ))}
              {profile.work_history.length === 0 && <p className="text-sm text-fg-3">No work history extracted.</p>}
            </div>
          </section>
          <section>
            <h4 className="mb-3 text-xs font-semibold uppercase tracking-wide text-fg-3">Skills · {skills.length}</h4>
            <div className="flex flex-wrap gap-1.5">{skills.map((s) => <Chip key={s}>{s}</Chip>)}</div>
          </section>
          {profile.education.length > 0 && (
            <section>
              <h4 className="mb-3 text-xs font-semibold uppercase tracking-wide text-fg-3">Education</h4>
              <ul className="space-y-2">
                {profile.education.map((e, i) => (
                  <li key={i} className="flex gap-2.5 text-sm">
                    <GraduationCap className="mt-0.5 size-4 shrink-0 text-fg-3" />
                    <span className="text-fg">
                      {[e.degree, e.field_of_study].filter(Boolean).join(', ') || 'Studies'}
                      <span className="text-fg-2"> · {e.institution}</span>
                      {e.end_year && <span className="text-fg-3"> · {e.end_year}</span>}
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          )}
          {profile.certifications.length > 0 && (
            <section>
              <h4 className="mb-3 text-xs font-semibold uppercase tracking-wide text-fg-3">Certifications</h4>
              <div className="flex flex-wrap gap-1.5">{profile.certifications.map((c) => <Chip key={c}>{c}</Chip>)}</div>
            </section>
          )}
        </div>
      )}
    </Card>
  )
}
