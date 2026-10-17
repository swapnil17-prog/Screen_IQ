import type {
  ApplicationDetail,
  ApplicationSummary,
  AuditLog,
  CandidateDetail,
  CandidateSummary,
  Dashboard,
  Evaluation,
  Fairness,
  Interview,
  InterviewListItem,
  JDBiasReport,
  JobDetail,
  JobSummary,
  Me,
  Meta,
  Organization,
  OrganizationSettings,
  Page,
  PublicInterview,
  PublicMessageResponse,
  Stage,
  UploadResult,
  User,
} from './types'

const BASE = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, '') ?? '/api/v1'

export class ApiError extends Error {
  status: number
  code: string
  requestId?: string

  constructor(status: number, code: string, message: string, requestId?: string) {
    super(message)
    this.status = status
    this.code = code
    this.requestId = requestId
  }
}

type Body = Record<string, unknown> | unknown[] | FormData | undefined

async function request<T>(method: string, path: string, body?: Body, signal?: AbortSignal): Promise<T> {
  const headers: Record<string, string> = { Accept: 'application/json' }
  let payload: BodyInit | undefined
  if (body instanceof FormData) payload = body
  else if (body !== undefined) {
    headers['Content-Type'] = 'application/json'
    payload = JSON.stringify(body)
  }

  let res: Response
  try {
    res = await fetch(`${BASE}${path}`, { method, headers, body: payload, credentials: 'include', signal })
  } catch (e) {
    if ((e as Error).name === 'AbortError') throw e
    throw new ApiError(0, 'network_error', 'Can’t reach the server. Check your connection and try again.')
  }

  if (res.status === 204) return undefined as T
  const data = await res.json().catch(() => null)
  if (!res.ok) {
    const err = data?.error
    throw new ApiError(
      res.status,
      err?.code ?? 'http_error',
      err?.message ?? `Request failed (${res.status})`,
      err?.request_id ?? res.headers.get('x-request-id') ?? undefined,
    )
  }
  return data as T
}

const get = <T,>(path: string, signal?: AbortSignal) => request<T>('GET', path, undefined, signal)
const post = <T,>(path: string, body?: Body) => request<T>('POST', path, body ?? {})
const patch = <T,>(path: string, body: Body) => request<T>('PATCH', path, body)
const del = <T,>(path: string) => request<T>('DELETE', path)

function qs(params: Record<string, string | number | boolean | undefined | null>): string {
  const q = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== null && v !== '') q.set(k, String(v))
  const s = q.toString()
  return s ? `?${s}` : ''
}

export const api = {
  meta: () => get<Meta>('/meta'),

  // Auth
  me: () => get<Me>('/auth/me'),
  login: (email: string, password: string) => post<Me & { access_token: string }>('/auth/login', { email, password }),
  register: (body: { organization_name: string; full_name: string; email: string; password: string }) =>
    post<Me & { access_token: string }>('/auth/register', body),
  logout: () => post<void>('/auth/logout'),
  changePassword: (current_password: string, new_password: string) =>
    post<void>('/auth/change-password', { current_password, new_password }),

  // Organization & team
  updateOrganization: (body: { name?: string; settings?: OrganizationSettings }) =>
    patch<Organization>('/organization', body),
  users: () => get<User[]>('/users'),
  inviteUser: (body: { email: string; full_name: string; role: string; temporary_password: string }) =>
    post<User>('/users', body),
  updateUser: (id: string, body: { role?: string; is_active?: boolean; full_name?: string }) =>
    patch<User>(`/users/${id}`, body),

  // Jobs
  jobs: (params: { status?: string; q?: string } = {}) => get<JobSummary[]>(`/jobs${qs(params)}`),
  job: (id: string) => get<JobDetail>(`/jobs/${id}`),
  createJob: (body: { title: string; description: string; department?: string; location?: string; employment_type?: string }) =>
    post<JobDetail>('/jobs', body),
  updateJob: (id: string, body: Record<string, unknown>) => patch<JobDetail>(`/jobs/${id}`, body),
  deleteJob: (id: string) => del<void>(`/jobs/${id}`),
  retryJobExtraction: (id: string) => post<JobDetail>(`/jobs/${id}/retry-extraction`),
  rescoreJob: (id: string) => post<{ queued: number }>(`/jobs/${id}/rescore`),
  biasCheck: (description: string, signal?: AbortSignal) =>
    request<JDBiasReport>('POST', '/jobs/bias-check', { description }, signal),
  jobApplications: (id: string, params: { stage?: string; tier?: string; sort?: string } = {}) =>
    get<ApplicationSummary[]>(`/jobs/${id}/applications${qs(params)}`),
  uploadResumes: (jobId: string, files: File[]) => {
    const form = new FormData()
    files.forEach((f) => form.append('files', f))
    return request<UploadResult>('POST', `/jobs/${jobId}/applications/upload`, form)
  },

  // Candidates
  candidates: (params: { q?: string; semantic?: boolean; limit?: number; offset?: number } = {}) =>
    get<Page<CandidateSummary>>(`/candidates${qs(params)}`),
  candidate: (id: string) => get<CandidateDetail>(`/candidates/${id}`),
  applyCandidate: (id: string, job_id: string) => post<ApplicationSummary>(`/candidates/${id}/applications`, { job_id }),
  reprocessCandidate: (id: string) => post<{ queued: number }>(`/candidates/${id}/reprocess`),
  deleteCandidate: (id: string) => del<void>(`/candidates/${id}`),

  // Applications
  application: (id: string) => get<ApplicationDetail>(`/applications/${id}`),
  updateApplication: (id: string, body: { stage?: Stage; notes?: string }) =>
    patch<ApplicationDetail>(`/applications/${id}`, body),
  rescreen: (id: string) => post<ApplicationDetail>(`/applications/${id}/rescreen`),
  createInterview: (id: string, replace = false) =>
    post<Interview>(`/applications/${id}/interview${replace ? '?replace=true' : ''}`),
  regenerateLink: (id: string) => post<Interview>(`/applications/${id}/interview/link`),
  cancelInterview: (id: string) => post<ApplicationDetail>(`/applications/${id}/interview/cancel`),
  runEvaluation: (id: string) => post<Evaluation>(`/applications/${id}/evaluation`),

  // Insights
  dashboard: (days = 7) => get<Dashboard>(`/dashboard?days=${days}`),
  fairness: () => get<Fairness>('/fairness'),
  interviews: (status?: string) => get<InterviewListItem[]>(`/interviews${qs({ status })}`),
  auditLogs: (params: { action?: string; limit?: number; offset?: number } = {}) =>
    get<Page<AuditLog>>(`/audit-logs${qs(params)}`),

  // Public candidate interview
  publicInterview: (token: string) => get<PublicInterview>(`/public/interviews/${token}`),
  startPublicInterview: (token: string) => post<PublicInterview>(`/public/interviews/${token}/start`, { consent: true }),
  sendPublicMessage: (token: string, message: string) =>
    post<PublicMessageResponse>(`/public/interviews/${token}/messages`, { message }),
}

