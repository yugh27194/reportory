-- 0001_init.sql
create extension if not exists vector;
create extension if not exists pgcrypto;

-- ===== enum =====
create type goal_type as enum ('grad_school','employment','undecided');
create type item_type as enum ('education','experience','project','activity',
  'award','certification','language_test','publication');
create type item_status as enum ('proposed','approved','rejected','archived');
create type visibility as enum ('private','public');
create type proposal_kind as enum ('create_item','update_item','link_entry',
  'merge_items','application_update','attach_evidence');
create type proposal_status as enum ('pending','accepted','rejected');
create type followup_status as enum ('open','answered','dismissed');
create type application_status as enum ('interested','applied','awaiting_result',
  'accepted','rejected','withdrawn','active','completed');
create type event_source as enum ('diary','reminder','manual','email','evidence','system');
create type opportunity_category as enum ('contest','hackathon','external_activity',
  'internship','research_internship','education','scholarship','other');
create type evidence_kind as enum ('language_score','certificate','award_certificate',
  'completion_certificate','other');
create type evidence_status as enum ('uploaded','processed','failed');
create type document_format as enum ('academic_cv','resume_en','resume_ko',
  'project_portfolio','web_profile');
create type job_status as enum ('queued','running','succeeded','failed');
create type import_source as enum ('resume_file','github','linkedin_zip','manual');
create type period_type as enum ('week','month');

-- ===== 공통 트리거 =====
create or replace function set_updated_at() returns trigger language plpgsql as $$
begin new.updated_at = now(); return new; end $$;

-- ===== profiles =====
create table profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  handle text unique check (handle ~ '^[a-z0-9_-]{3,30}$'),
  display_name text,
  display_name_en text,
  email_public text,
  links jsonb not null default '[]',          -- [{"label","url"}]
  goal goal_type not null default 'undecided',
  interests text[] not null default '{}',
  target_roles text[] not null default '{}',
  school text, major text, grade smallint check (grade between 1 and 6),
  region text,
  public_profile_enabled boolean not null default false,
  llm_consent_at timestamptz,                  -- LLM 처리 동의 시각
  onboarding_completed_at timestamptz,
  notify_email boolean not null default false,
  profile_embedding vector(1536),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- ===== entries =====
create table entries (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  entry_date date not null,
  body text not null check (char_length(body) between 1 and 20000),
  extraction_status job_status,
  extracted_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index entries_user_date on entries(user_id, entry_date desc);

-- ===== imports =====
create table imports (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  source import_source not null,
  status job_status not null default 'queued',
  storage_path text,
  summary jsonb not null default '{}',         -- {"items_proposed": n, ...}
  error text,
  created_at timestamptz not null default now(),
  finished_at timestamptz
);

-- ===== opportunities (전역) =====
create table opportunities (
  id uuid primary key default gen_random_uuid(),
  source_url text not null unique,
  source_site text,
  title text not null,
  organizer text,
  category opportunity_category not null default 'other',
  summary text,
  eligibility jsonb not null default '{}',     -- 10.6절 Eligibility
  benefits text,
  apply_start date, apply_deadline date, result_announce_on date,
  activity_start date, activity_end date,
  location text, is_online boolean,
  tags text[] not null default '{}',
  embedding vector(1536),
  is_active boolean not null default true,
  created_by uuid references auth.users(id) on delete cascade, -- 사용자가 URL로 추가한 경우
  fetched_at timestamptz not null default now(),
  created_at timestamptz not null default now()
);
create index opportunities_deadline on opportunities(apply_deadline) where is_active;

-- ===== items =====
create table items (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  type item_type not null,
  status item_status not null default 'proposed',
  title text not null,
  title_en text,
  organization text,
  role text,
  start_date date, end_date date,
  is_ongoing boolean not null default false,
  summary text not null default '',
  details jsonb not null default '{}',         -- 유형별 필드(10.2절)
  metrics jsonb not null default '[]',         -- [{"name","value","unit"}]
  links jsonb not null default '[]',           -- [{"label","url"}]
  visibility visibility not null default 'private',
  embedding vector(1536),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  approved_at timestamptz
);
create index items_user_status on items(user_id, status);

create table skills (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  normalized text not null unique,             -- 소문자, 공백·구두점 제거
  category text check (category in ('language','framework','library','tool',
    'platform','method','domain','soft'))
);

create table item_skills (
  item_id uuid not null references items(id) on delete cascade,
  skill_id uuid not null references skills(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  primary key (item_id, skill_id)
);

-- ===== evidence =====
create table evidence (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  item_id uuid references items(id) on delete set null,
  kind evidence_kind,
  status evidence_status not null default 'uploaded',
  storage_path text not null,                  -- evidence/{user_id}/{uuid}.{ext}
  masked_path text,
  file_name text not null,
  mime_type text not null,
  size_bytes integer not null check (size_bytes <= 10485760),
  ocr_text text,
  extracted jsonb not null default '{}',       -- 10.10절 EvidenceExtract
  issued_on date, expires_on date,
  visibility visibility not null default 'private',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- ===== item_sources =====
create table item_sources (
  id uuid primary key default gen_random_uuid(),
  item_id uuid not null references items(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  entry_id uuid references entries(id) on delete cascade,
  import_id uuid references imports(id) on delete cascade,
  evidence_id uuid references evidence(id) on delete cascade,
  followup_id uuid,                            -- FK는 followup_questions 생성 후 추가
  quote text,
  created_at timestamptz not null default now(),
  check (num_nonnulls(entry_id, import_id, evidence_id, followup_id) >= 1)
);
create index item_sources_item on item_sources(item_id);

-- ===== documents =====
create table documents (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  format document_format not null,
  title text not null,
  target_description text,
  language text not null default 'ko' check (language in ('ko','en')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table document_versions (
  id uuid primary key default gen_random_uuid(),
  document_id uuid not null references documents(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  version integer not null,
  selected_item_ids uuid[] not null,
  options jsonb not null default '{}',
  content jsonb,                               -- JSON Resume + x- 확장
  pdf_path text,                               -- documents/{user_id}/{uuid}.pdf
  status job_status not null default 'queued',
  created_at timestamptz not null default now(),
  unique (document_id, version)
);

-- ===== applications =====
create table applications (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  opportunity_id uuid references opportunities(id) on delete set null,
  title text not null,
  organizer text,
  category opportunity_category not null default 'other',
  status application_status not null default 'interested',
  apply_deadline date,
  applied_at date,
  result_announce_on date,
  result_at date,
  activity_start date, activity_end date,
  result_note text,
  reflection text,
  item_id uuid references items(id) on delete set null,
  submitted_version_id uuid references document_versions(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index applications_user_status on applications(user_id, status);

create table application_events (
  id uuid primary key default gen_random_uuid(),
  application_id uuid not null references applications(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  from_status application_status,
  to_status application_status not null,
  source event_source not null,
  entry_id uuid references entries(id) on delete set null,
  note text,
  created_at timestamptz not null default now()
);

-- ===== proposals / followups =====
create table proposals (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  kind proposal_kind not null,
  status proposal_status not null default 'pending',
  payload jsonb not null,
  item_id uuid references items(id) on delete cascade,
  application_id uuid references applications(id) on delete cascade,
  entry_id uuid references entries(id) on delete cascade,
  import_id uuid references imports(id) on delete cascade,
  evidence_id uuid references evidence(id) on delete cascade,
  confidence real check (confidence between 0 and 1),
  quote text,
  possible_duplicate_of uuid references items(id) on delete set null,
  created_at timestamptz not null default now(),
  resolved_at timestamptz
);
create index proposals_user_status on proposals(user_id, status, created_at desc);

create table followup_questions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  item_id uuid not null references items(id) on delete cascade,
  entry_id uuid references entries(id) on delete set null,
  question text not null,
  reason text,
  answer text,
  status followup_status not null default 'open',
  created_at timestamptz not null default now(),
  answered_at timestamptz
);
alter table item_sources add constraint item_sources_followup_fk
  foreign key (followup_id) references followup_questions(id) on delete cascade;

-- ===== summaries / recommendations =====
create table period_summaries (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  period period_type not null,
  period_start date not null,
  period_end date not null,
  summary_md text not null,
  highlights jsonb not null default '[]',      -- [{"item_id","text"}]
  created_at timestamptz not null default now(),
  unique (user_id, period, period_start)
);

create table recommendations (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  opportunity_id uuid not null references opportunities(id) on delete cascade,
  score real not null,
  score_breakdown jsonb not null default '{}', -- {"sim","gap","pref","urgency"}
  reason text,
  reason_item_ids uuid[] not null default '{}',
  feedback text check (feedback in ('interested','dismissed','applied')),
  generated_at timestamptz not null default now(),
  feedback_at timestamptz,
  unique (user_id, opportunity_id)
);

-- ===== jobs / notifications / llm_calls =====
create table jobs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) on delete cascade,
  type text not null,
  payload jsonb not null default '{}',
  status job_status not null default 'queued',
  attempts integer not null default 0,
  max_attempts integer not null default 3,
  run_after timestamptz not null default now(),
  locked_at timestamptz,
  last_error text,
  result jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index jobs_ready on jobs(status, run_after);

create table notifications (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  type text not null,                          -- 11.8절
  title text not null,
  body text,
  link text,
  read_at timestamptz,
  created_at timestamptz not null default now()
);

create table llm_calls (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) on delete set null,
  purpose text not null,                       -- extract_entry, rewrite_doc, ...
  provider text not null, model text not null,
  prompt_version text not null,
  input_tokens integer, output_tokens integer,
  latency_ms integer, success boolean not null,
  error text,
  created_at timestamptz not null default now()
);

-- ===== updated_at 트리거 =====
do $$ declare t text; begin
  foreach t in array array['profiles','entries','items','evidence','documents',
                           'applications','jobs'] loop
    execute format('create trigger %I_updated before update on %I
                    for each row execute function set_updated_at()', t, t);
  end loop;
end $$;

-- ===== RLS =====
alter table profiles enable row level security;
create policy own_profile on profiles for all
  using (id = auth.uid()) with check (id = auth.uid());

do $$ declare t text; begin
  foreach t in array array['entries','imports','items','item_skills','evidence',
    'item_sources','documents','document_versions','applications',
    'application_events','proposals','followup_questions','period_summaries',
    'recommendations','notifications'] loop
    execute format('alter table %I enable row level security', t);
    execute format('create policy own_rows on %I for all
                    using (user_id = auth.uid()) with check (user_id = auth.uid())', t);
  end loop;
end $$;

-- 조회 전용(쓰기는 service role만)
alter table jobs enable row level security;
create policy own_jobs_read on jobs for select using (user_id = auth.uid());
alter table llm_calls enable row level security;
create policy own_llm_read on llm_calls for select using (user_id = auth.uid());
alter table skills enable row level security;
create policy skills_read on skills for select to authenticated using (true);
alter table opportunities enable row level security;
create policy opp_read on opportunities for select to authenticated
  using (created_by is null or created_by = auth.uid());

-- ===== 임베딩 인덱스 =====
create index items_embedding on items using hnsw (embedding vector_cosine_ops);
create index opp_embedding on opportunities using hnsw (embedding vector_cosine_ops);

-- ===== Storage 버킷(모두 비공개) =====
insert into storage.buckets (id, name, public) values
  ('evidence','evidence',false), ('imports','imports',false),
  ('documents','documents',false), ('exports','exports',false)
on conflict (id) do nothing;
