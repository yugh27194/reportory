-- 0002_phase2.sql: Phase 2(가져오기, 증빙, 문서, 요약, 알림)에 필요한 열을 더한다.

-- 주간·월간 요약(10.5절)이 쓰는 일기 한 줄 요약
alter table entries add column if not exists summary text;

-- 같은 대상에 같은 알림을 두 번 보내지 않기 위한 참조 id(증빙 만료, 요약 생성 등)
alter table notifications add column if not exists ref_id uuid;
create unique index if not exists notifications_dedupe
  on notifications(user_id, type, ref_id) where ref_id is not null;
create index if not exists notifications_user_created on notifications(user_id, created_at desc);

-- 공개 프로필에 PDF 링크를 보일 문서(11.9절 Phase 2 확장)
alter table documents add column if not exists is_public boolean not null default false;

-- 증빙 목록·만료 알림 조회
create index if not exists evidence_user_item on evidence(user_id, item_id);
create index if not exists evidence_expires on evidence(expires_on) where expires_on is not null;

-- 공개 프로필 한 줄 소개(11.9절)
alter table profiles add column if not exists headline text check (char_length(headline) <= 120);
