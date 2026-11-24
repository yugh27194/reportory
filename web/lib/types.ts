export type ItemType =
  | "education"
  | "experience"
  | "project"
  | "activity"
  | "award"
  | "certification"
  | "language_test"
  | "publication";

export const ITEM_TYPE_LABELS: Record<ItemType, string> = {
  education: "학력",
  experience: "경력",
  project: "프로젝트",
  activity: "활동",
  award: "수상",
  certification: "자격증",
  language_test: "어학",
  publication: "논문",
};

/** 포트폴리오 화면의 섹션 순서(인계서 11.2절). */
export const ITEM_TYPE_ORDER: ItemType[] = [
  "education",
  "experience",
  "project",
  "activity",
  "award",
  "certification",
  "language_test",
  "publication",
];

export type Metric = { name: string; value: string; unit?: string | null };

export type Item = {
  id: string;
  type: ItemType;
  status: "proposed" | "approved" | "rejected" | "archived";
  title: string;
  title_en: string | null;
  organization: string | null;
  role: string | null;
  start_date: string | null;
  end_date: string | null;
  is_ongoing: boolean;
  summary: string;
  details: Record<string, unknown>;
  metrics: Metric[];
  links: { label: string; url: string }[];
  visibility: "private" | "public";
  skills?: string[];
  source_count?: number;
  evidence_count?: number;
};

export type ItemSource = {
  id: string;
  entry_id: string | null;
  import_id: string | null;
  evidence_id: string | null;
  followup_id: string | null;
  quote: string | null;
  entry_date: string | null;
};

export type ItemDetail = Item & {
  skills: string[];
  sources: ItemSource[];
  evidence: Evidence[];
  applications: { id: string; title: string; status: string }[];
};

export type Entry = {
  id: string;
  entry_date: string;
  body: string;
  extraction_status: "queued" | "running" | "succeeded" | "failed" | null;
  created_at: string;
};

export type ProposalKind =
  | "create_item"
  | "update_item"
  | "link_entry"
  | "merge_items"
  | "application_update"
  | "attach_evidence";

export const PROPOSAL_KIND_LABELS: Record<ProposalKind, string> = {
  create_item: "새 항목",
  update_item: "항목 갱신",
  link_entry: "근거 연결",
  merge_items: "항목 병합",
  application_update: "지원 결과",
  attach_evidence: "증빙 연결",
};

export type Proposal = {
  id: string;
  kind: ProposalKind;
  status: string;
  payload: Record<string, unknown>;
  item_id: string | null;
  entry_id: string | null;
  confidence: number | null;
  quote: string | null;
  possible_duplicate_of: string | null;
  created_at: string;
  entry_date: string | null;
  entry_body: string | null;
  item: Item | null;
  item_skills: string[];
  duplicate: Item | null;
  import_source: ImportRow["source"] | null;
  evidence_file_name: string | null;
  evidence_kind: string | null;
};

export type Followup = {
  id: string;
  item_id: string;
  question: string;
  reason: string | null;
  item_title: string;
  item_type: ItemType;
};

export type Job = {
  id: string;
  status: "queued" | "running" | "succeeded" | "failed";
  result: Record<string, unknown> | null;
  last_error: string | null;
};

export type Profile = {
  id: string;
  handle: string | null;
  display_name: string | null;
  display_name_en: string | null;
  email_public: string | null;
  links: { label: string; url: string }[];
  goal: "grad_school" | "employment" | "undecided";
  interests: string[];
  target_roles: string[];
  school: string | null;
  major: string | null;
  grade: number | null;
  region: string | null;
  public_profile_enabled: boolean;
  llm_consent_at: string | null;
  headline: string | null;
  onboarding_completed_at: string | null;
  notify_email: boolean;
};

/** details 키의 화면 표시 이름(인계서 10.2절 유형별 details). */
export const DETAIL_LABELS: Record<string, string> = {
  rank: "순위",
  competition: "대회",
  host: "주최",
  issuer: "발급기관",
  cert_number_last4: "번호 끝 4자리",
  test: "시험",
  score: "점수",
  level: "등급",
  test_date: "응시일",
  valid_until: "유효기간",
  team_size: "팀 규모",
  repo_url: "저장소",
  demo_url: "데모",
  employment_type: "고용 형태",
  lab_or_team: "연구실·팀",
  venue: "학회·저널",
  authors: "저자",
  status: "상태",
  doi: "DOI",
  degree: "학위",
  major: "전공",
  gpa: "학점",
};

export const detailText = (details: Record<string, unknown>) =>
  Object.entries(details)
    .map(([k, v]) => `${DETAIL_LABELS[k] ?? k}: ${String(v)}`)
    .join(", ");

export type Evidence = {
  id: string;
  item_id: string | null;
  kind: "language_score" | "certificate" | "award_certificate" | "completion_certificate" | "other" | null;
  status: "uploaded" | "processed" | "failed";
  file_name: string;
  mime_type: string;
  visibility: "private" | "public";
  issued_on: string | null;
  expires_on: string | null;
  extracted: Record<string, unknown>;
  created_at: string;
};

export const EVIDENCE_KIND_LABELS: Record<string, string> = {
  language_score: "어학 성적",
  certificate: "자격증",
  award_certificate: "상장",
  completion_certificate: "수료증",
  other: "기타",
};

export type DocFormat = "academic_cv" | "resume_en" | "resume_ko" | "project_portfolio";

export const DOC_FORMATS: { key: DocFormat; label: string; desc: string }[] = [
  { key: "resume_ko", label: "국문 이력서", desc: "국내 기업·공공기관용. 자격증·어학은 표로 정리한다." },
  { key: "resume_en", label: "영문 Resume", desc: "외국계·해외 지원용 A4 1쪽. 행동 동사로 시작하는 bullet이다." },
  { key: "academic_cv", label: "Academic CV", desc: "대학원·연구실·연구 인턴용. 연구 경험을 앞에 둔다." },
  {
    key: "project_portfolio",
    label: "프로젝트 포트폴리오",
    desc: "개발·데이터 직무용. 표지와 프로젝트별 쪽으로 만든다.",
  },
];

export type DocumentRow = {
  id: string;
  format: DocFormat;
  title: string;
  target_description: string | null;
  language: "ko" | "en";
  is_public: boolean;
  created_at: string;
  updated_at: string;
  latest?: { version: number; status: string; created_at: string } | null;
};

export type DocVersion = {
  id: string;
  version: number;
  selected_item_ids: string[];
  options: { warnings?: string[]; dropped_lines?: number; removed_items?: string[] };
  status: "queued" | "running" | "succeeded" | "failed";
  has_pdf: boolean;
  created_at: string;
  content?: DocContent | null;
  html?: string | null;
};

export type DocContent = {
  "x-reportory": {
    format: DocFormat;
    sections: { key: string; label: string; items: string[] }[];
    items: Record<
      string,
      {
        title: string;
        type: ItemType;
        organization: string | null;
        role: string | null;
        period: [string | null, string | null];
        is_ongoing: boolean;
        skills: string[];
        details: Record<string, unknown>;
        lines: string[];
      }
    >;
  };
  skills?: { name: string; keywords: string[] }[];
};

export type RankedItem = {
  id: string;
  type: ItemType;
  title: string;
  title_en: string | null;
  organization: string | null;
  start_date: string | null;
  end_date: string | null;
  is_ongoing: boolean;
  score: number;
  selected: boolean;
};

export type ImportRow = {
  id: string;
  source: "resume_file" | "github" | "linkedin_zip" | "manual";
  status: "queued" | "running" | "succeeded" | "failed";
  summary: { items_proposed?: number; merged?: number; skipped?: string[]; repos?: number };
  error: string | null;
  created_at: string;
};

export type Notification = {
  id: string;
  type: string;
  title: string;
  body: string | null;
  link: string | null;
  read_at: string | null;
  created_at: string;
};

export type PeriodSummary = {
  id: string;
  period: "day" | "week" | "month";
  period_start: string;
  period_end: string;
  summary_md: string;
  highlights: { item_id: string; text: string }[];
};

export type Stats = {
  items_by_type: Partial<Record<ItemType, number>>;
  items_total: number;
  pending_proposals: number;
  open_followups: number;
  entries: { total: number; this_week: number; days_this_month: number };
  documents: number;
  evidence: number;
  recent_items: { id: string; type: ItemType; title: string; organization: string | null; approved_at: string }[];
  latest_summary: PeriodSummary | null;
};

export type RadarAxis =
  | "experience"
  | "project"
  | "activity"
  | "award"
  | "certification"
  | "language_test"
  | "publication";
export type SpecPreset = "dev_job" | "biz_job" | "public_job" | "grad_school" | "custom";

export type Growth = {
  stage: { level: number; key: string; label: string; score: number; next_at: number | null; progress: number };
  items_total: number;
  entry_days: number;
  counts: Partial<Record<ItemType, number>>;
  radar: {
    axes: RadarAxis[];
    values: Record<RadarAxis, number>;
    target: { preset: SpecPreset; values: Record<RadarAxis, number> };
  };
  presets: Record<string, { label: string; values: Record<RadarAxis, number> }>;
};

export type JournalCalendar = {
  year: number;
  years: number[];
  days: Record<string, { entries: number; chars: number; items: number }>;
};

export type OpportunityCategory =
  | "contest"
  | "hackathon"
  | "external_activity"
  | "internship"
  | "research_internship"
  | "education"
  | "scholarship"
  | "other";

export const CATEGORY_LABELS: Record<OpportunityCategory, string> = {
  contest: "공모전",
  hackathon: "해커톤",
  external_activity: "대외활동",
  internship: "인턴십",
  research_internship: "연구 인턴",
  education: "교육",
  scholarship: "장학금",
  other: "기타",
};

export type Recommendation = {
  id: string;
  score: number;
  score_breakdown: { sim: number; gap: number; pref: number; urgency: number };
  reason: string | null;
  feedback: "interested" | "dismissed" | "applied" | null;
  opportunity_id: string;
  title: string;
  organizer: string | null;
  category: OpportunityCategory;
  summary: string | null;
  source_url: string;
  source_site: string | null;
  apply_deadline: string | null;
  activity_start: string | null;
  activity_end: string | null;
  benefits: string | null;
  location: string | null;
  is_online: boolean | null;
  tags: string[];
  added_by_me: boolean;
  reason_items: { id: string; title: string; type: ItemType }[];
};

export type ApplicationStatus =
  | "interested"
  | "applied"
  | "awaiting_result"
  | "accepted"
  | "rejected"
  | "withdrawn"
  | "active"
  | "completed";

export const APPLICATION_STATUS_LABELS: Record<ApplicationStatus, string> = {
  interested: "관심",
  applied: "지원함",
  awaiting_result: "결과 대기",
  accepted: "합격",
  rejected: "불합격",
  withdrawn: "취소",
  active: "활동 중",
  completed: "완료",
};

/** 화면에서 고를 수 있는 다음 상태(인계서 8.3절, 자동 전이는 뺀다). */
export const NEXT_STATUSES: Record<ApplicationStatus, ApplicationStatus[]> = {
  interested: ["applied", "withdrawn"],
  applied: ["accepted", "rejected", "withdrawn"],
  awaiting_result: ["accepted", "rejected", "withdrawn"],
  accepted: ["active"],
  active: ["completed"],
  rejected: [],
  withdrawn: [],
  completed: [],
};

export type Application = {
  id: string;
  opportunity_id: string | null;
  title: string;
  organizer: string | null;
  category: OpportunityCategory;
  status: ApplicationStatus;
  apply_deadline: string | null;
  applied_at: string | null;
  result_announce_on: string | null;
  result_at: string | null;
  activity_start: string | null;
  activity_end: string | null;
  result_note: string | null;
  reflection: string | null;
  item_id: string | null;
  created_at: string;
};

export type ApplicationDetail = Application & {
  events: {
    from_status: ApplicationStatus | null;
    to_status: ApplicationStatus;
    source: string;
    note: string | null;
    created_at: string;
  }[];
  opportunity: {
    id: string;
    source_url: string;
    summary: string | null;
    benefits: string | null;
    tags: string[];
  } | null;
};
