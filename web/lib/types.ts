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
