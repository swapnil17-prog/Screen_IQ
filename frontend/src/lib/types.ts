// Mirrors backend/app/schemas/*. Keep in sync with the API.

export type Role = 'owner' | 'admin' | 'recruiter' | 'viewer'
export type Stage = 'new' | 'shortlisted' | 'interviewing' | 'offer' | 'hired' | 'rejected'
export type PipelineStatus =
  | 'queued' | 'parsing' | 'extracting' | 'analyzing' | 'matching' | 'scoring' | 'completed' | 'failed'
export type ScreeningLabel = 'strong_match' | 'good_match' | 'potential' | 'weak_match'
export type Recommendation = 'strong_hire' | 'hire' | 'lean_hire' | 'lean_no_hire' | 'no_hire'
export type InterviewStatus = 'pending' | 'in_progress' | 'completed' | 'expired' | 'cancelled'
export type Tier = 'strong' | 'review' | 'low'

export interface Page<T> {
  items: T[]
  total: number
  limit: number
  offset: number
}

// ── Auth / org ────────────────────────────────────────────────────────────────
export interface User {
  id: string
  email: string
  full_name: string
  role: Role
  is_active: boolean
  last_login_at: string | null
  created_at: string
}

export interface ScoringWeights {
  skills: number
  experience: number
  semantic: number
  assessment: number
}

export interface OrganizationSettings {
  blind_screening: boolean
  scoring_weights: ScoringWeights
  final_weights: { screening: number; interview: number }
  interview_question_count: number
  interview_max_follow_ups: number
  auto_invite_on_shortlist: boolean
  bias_delta_threshold: number
}

export interface Organization {
  id: string
  name: string
  slug: string
  settings: OrganizationSettings
  created_at: string
}

export interface Me {
  user: User
  organization: Organization
}

export interface Meta {
  version: string
  environment: string
  llm_provider: 'anthropic' | 'mock'
  llm_model: string
  embedding_provider: 'bge' | 'openai' | 'hash'
  email_delivery: 'smtp' | 'console'
  allow_public_signup: boolean
  max_upload_mb: number
  max_files_per_upload: number
}

// ── Jobs ──────────────────────────────────────────────────────────────────────
export interface JDExtraction {
  role_title: string
  seniority: string | null
  required_skills: string[]
  nice_to_have_skills: string[]
  min_years_experience: number | null
  education_requirement: string | null
  responsibilities: string[]
  domain: string | null
}

export interface BiasFlag {
  category: 'masculine_coded' | 'feminine_coded' | 'age' | 'exclusionary' | 'ableist' | 'jargon' | 'requirements'
  phrase: string
  count: number
  severity: 'low' | 'medium' | 'high'
  suggestion: string
}

export interface JDBiasReport {
  score: number
  rating: 'inclusive' | 'needs_review' | 'biased'
  gender_lean: 'masculine' | 'feminine' | 'neutral'
  masculine_count: number
  feminine_count: number
  word_count: number
  flags: BiasFlag[]
  summary: string
}

export interface JobCounts {
  total: number
  screened: number
  processing: number
  failed: number
  shortlisted: number
  interviewing: number
  hired: number
  strong: number
  review: number
  low: number
}

export interface JobSummary {
  id: string
  title: string
  department: string | null
  location: string | null
  employment_type: string | null
  status: 'open' | 'paused' | 'closed' | 'archived'
  extraction_status: 'pending' | 'completed' | 'failed'
  created_at: string
  updated_at: string
  counts: JobCounts
  avg_score: number | null
  top_score: number | null
  inclusivity_score: number | null
}

export interface JobDetail extends JobSummary {
  description: string
  extracted: JDExtraction | null
  extraction_error: string | null
  bias_report: JDBiasReport | null
  scoring_weights: ScoringWeights
  has_custom_weights: boolean
}

// ── Candidates & screening ────────────────────────────────────────────────────
export interface CandidateRef {
  id: string
  full_name: string | null
  headline: string | null
  current_company: string | null
  email: string | null
  location: string | null
}

export interface ApplicationSummary {
  id: string
  job_id: string
  job_title: string | null
  candidate: CandidateRef
  stage: Stage
  status: PipelineStatus
  error: string | null
  screening_score: number | null
  screening_label: ScreeningLabel | null
  tier: Tier | null
  one_liner: string | null
  skill_chips: { skill: string; importance: 'required' | 'nice_to_have'; status: 'matched' | 'partial' | 'missing' }[]
  final_score: number | null
  recommendation: Recommendation | null
  confidence: 'high' | 'medium' | 'low' | null
  required_coverage_pct: number | null
  missing_required: string[]
  total_years: number | null
  flags: string[]
  interview_status: InterviewStatus | null
  created_at: string
  updated_at: string
}

export interface SkillMatch {
  skill: string
  importance: 'required' | 'nice_to_have'
  status: 'matched' | 'partial' | 'missing'
  method: 'exact' | 'alias' | 'related' | 'semantic' | 'mentioned' | 'none'
  matched_to: string | null
  similarity: number | null
}

export interface SkillGap {
  matches: SkillMatch[]
  matched_required: string[]
  partial_required: string[]
  missing_required: string[]
  matched_nice_to_have: string[]
  missing_nice_to_have: string[]
  bonus_skills: string[]
  required_coverage_pct: number
  nice_to_have_coverage_pct: number
}

export interface ExperienceRole {
  company: string
  title: string
  start: string | null
  end: string | null
  months: number | null
  is_current: boolean
  seniority: string | null
}

export interface ExperienceAnalysis {
  total_years: number | null
  role_count: number
  roles: ExperienceRole[]
  average_tenure_months: number | null
  longest_tenure_months: number | null
  gaps: { start: string; end: string; months: number }[]
  current_title: string | null
  current_company: string | null
  seniority_estimate: string | null
  progression: 'ascending' | 'stable' | 'mixed' | 'unknown'
  flags: string[]
}

export interface EvidenceChunk {
  id: string
  section: string
  text: string
  similarity: number
}

export interface RequirementAssessment {
  id: string
  requirement: string
  kind: 'skill' | 'responsibility' | 'experience' | 'education'
  importance: 'required' | 'nice_to_have'
  verdict: 'met' | 'partial' | 'not_met'
  reasoning: string
  evidence_quote: string | null
  quote_verified: boolean
  evidence: EvidenceChunk[]
}

export type ComponentKey = 'skills' | 'experience' | 'semantic' | 'assessment'

export interface ScoreComponent {
  key: ComponentKey
  label: string
  score: number
  weight: number
  contribution: number
  reasons: string[]
}

export interface ScreeningResult {
  version: string
  overall_score: number
  label: ScreeningLabel
  confidence: 'high' | 'medium' | 'low'
  components: ScoreComponent[]
  summary: string
  one_liner: string
  strengths: string[]
  concerns: string[]
  flags: string[]
  skill_gap: SkillGap
  experience_fit: {
    candidate_years: number | null
    required_years: number | null
    expected_seniority: string | null
    estimated_seniority: string | null
    relevant_roles: { title: string; company: string; relevance: number }[]
  }
  semantic: { score: number; sections: { section: string; similarity: number; calibrated: number }[] }
  requirements: RequirementAssessment[]
  blind_screening: boolean
  redactions: Record<string, number>
  llm_provider: string
  llm_model: string
  embedding_provider: string
  generated_at: string
}

export interface ResumeExtraction {
  full_name: string | null
  email: string | null
  phone: string | null
  location: string | null
  headline: string | null
  summary: string | null
  skills: string[]
  education: { institution: string; degree: string | null; field_of_study: string | null; start_year: number | null; end_year: number | null }[]
  work_history: { company: string; title: string; location: string | null; start_date: string | null; end_date: string | null; highlights: string[] }[]
  certifications: string[]
  languages: string[]
  links: string[]
}

// ── Interviews & evaluation ───────────────────────────────────────────────────
export interface InterviewQuestion {
  id: string
  category: 'technical' | 'behavioral' | 'gap_probe' | 'experience_deep_dive' | 'situational'
  topic: string
  question: string
  rationale: string
  ideal_answer_criteria: string[]
  related_requirement: string | null
}

export interface InterviewPlan {
  strategy: string
  questions: InterviewQuestion[]
  max_follow_ups: number
  estimated_minutes: number
  generated_by: string
}

export interface ChatMessage {
  role: 'assistant' | 'candidate'
  content: string
  timestamp: string
  question_id: string | null
  kind: 'greeting' | 'question' | 'follow_up' | 'acknowledgement' | 'answer' | 'closing'
}

export interface Interview {
  id: string
  application_id: string
  status: InterviewStatus
  plan: InterviewPlan
  current_question_index: number
  answered_questions: number
  messages: ChatMessage[]
  consent_at: string | null
  started_at: string | null
  completed_at: string | null
  expires_at: string
  created_at: string
  link: string | null
}

export interface QuestionScore {
  question_id: string
  technical_depth: number
  communication: number
  problem_solving: number
  score: number
  criteria: { criterion: string; met: boolean; evidence_quote: string | null; score: number }[]
  strengths: string[]
  improvements: string[]
}

export interface BiasAudit {
  method: string
  unmasked_score: number
  masked_score: number
  delta: number
  threshold: number
  risk: 'low' | 'medium' | 'high'
  flagged: boolean
  entities_masked: Record<string, number>
  per_question: { question_id: string; unmasked: number; masked: number; delta: number }[]
  explanation: string
  notes: string[]
}

export interface Evaluation {
  id: string
  application_id: string
  interview_session_id: string
  status: 'running' | 'completed' | 'failed'
  error: string | null
  composite_score: number | null
  recommendation: Recommendation | null
  screening_score: number | null
  interview_score: number | null
  components: { key: 'screening' | 'interview'; label: string; score: number; weight: number; contribution: number }[]
  rubric: {
    overall_score: number
    summary: string
    question_scores: QuestionScore[]
    key_strengths: string[]
    key_risks: string[]
  } | null
  bias_audit: BiasAudit | null
  audit_trace: Record<string, unknown> | null
  created_at: string
  updated_at: string
}

export interface ApplicationDetail extends ApplicationSummary {
  notes: string | null
  filename: string
  raw_text: string
  stage_changed_by: string | null
  stage_changed_at: string | null
  screened_at: string | null
  screening: ScreeningResult | null
  candidate_profile: ResumeExtraction | null
  experience: ExperienceAnalysis | null
  skills: string[]
  interview: Interview | null
  evaluation: Evaluation | null
}

export interface UploadResult {
  created: ApplicationSummary[]
  duplicates: ApplicationSummary[]
  errors: { filename: string; message: string }[]
}

export interface CandidateSummary {
  id: string
  full_name: string | null
  email: string | null
  headline: string | null
  location: string | null
  status: 'processing' | 'ready' | 'failed'
  error: string | null
  skills: string[]
  total_years: number | null
  applications_count: number
  created_at: string
  similarity: number | null
}

export interface CandidateDetail extends CandidateSummary {
  phone: string | null
  filename: string
  file_size: number
  extracted: ResumeExtraction | null
  experience: ExperienceAnalysis | null
  raw_text: string
  applications: {
    id: string
    job_id: string
    job_title: string
    stage: Stage
    status: PipelineStatus
    screening_score: number | null
    final_score: number | null
    created_at: string
  }[]
}

export interface InterviewListItem {
  id: string
  application_id: string
  job_id: string
  job_title: string
  candidate_name: string | null
  status: InterviewStatus
  answered_questions: number
  total_questions: number
  created_at: string
  completed_at: string | null
  expires_at: string
  final_score: number | null
  recommendation: Recommendation | null
}

export interface PublicInterview {
  organization_name: string
  job_title: string
  candidate_first_name: string | null
  status: InterviewStatus
  question_count: number
  answered_questions: number
  estimated_minutes: number
  expires_at: string
  consent_given: boolean
  messages: ChatMessage[]
}

export interface PublicMessageResponse {
  new_messages: ChatMessage[]
  status: InterviewStatus
  answered_questions: number
  question_count: number
  completed: boolean
}

// ── Insights ──────────────────────────────────────────────────────────────────
export interface CountBucket {
  key: string
  label: string
  count: number
}

export interface ActivityItem {
  id: string
  action: string
  actor_type: 'user' | 'candidate' | 'system'
  actor_name: string | null
  entity_type: string | null
  entity_id: string | null
  details: Record<string, unknown>
  created_at: string
}

export interface Metric {
  value: number | null
  previous: number | null
  delta: number | null
}

export interface Dashboard {
  period: {
    days: number
    screened: Metric
    avg_score: Metric
    shortlisted: Metric
    avg_seconds_to_screen: Metric
  }
  needs_review: { application_id: string; candidate_name: string | null; job_title: string; score: number; reason: string | null }[]
  needs_review_total: number
  kpis: {
    open_jobs: number
    candidates: number
    applications: number
    screened: number
    avg_screening_score: number | null
    interviews_completed: number
    interviews_active: number
    evaluations: number
    flagged_evaluations: number
  }
  funnel: CountBucket[]
  score_distribution: CountBucket[]
  recent_activity: ActivityItem[]
  top_candidates: {
    application_id: string
    candidate_name: string | null
    job_title: string
    score: number
    label: ScreeningLabel | null
    final_score: number | null
  }[]
}

export interface Fairness {
  blind_screening: boolean
  bias_delta_threshold: number
  avg_inclusivity: number | null
  jobs: { job_id: string; title: string; score: number; rating: JDBiasReport['rating']; gender_lean: string; flags: number; high_severity: number }[]
  evaluations_total: number
  evaluations_flagged: number
  avg_abs_delta: number | null
  risk_counts: Record<'low' | 'medium' | 'high', number>
  redactions: Record<string, number>
  screenings_blind: number
  flagged_evaluations: { application_id: string; candidate_name: string | null; job_title: string; delta: number; risk: string; created_at: string }[]
  injection_flags: number
}

export interface AuditLog extends ActivityItem {
  ip_address: string | null
}
