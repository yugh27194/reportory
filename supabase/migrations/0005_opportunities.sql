-- 0005_opportunities.sql: 활동 추천(Phase 3).
-- 같은 공고 URL이 '모두에게 보이는 수집 공고' 하나와 '사용자가 직접 추가한 공고'(사용자마다 하나)로
-- 따로 있을 수 있게 한다. 다른 사람이 추가한 공고가 내게 보이지 않게 하기 위해서다.
alter table opportunities drop constraint if exists opportunities_source_url_key;
create unique index if not exists opportunities_url_shared
  on opportunities(source_url) where created_by is null;
create unique index if not exists opportunities_url_private
  on opportunities(source_url, created_by) where created_by is not null;

-- 추천 근거 항목과 점수 계산에 쓰는 보조 인덱스
create index if not exists recommendations_user_score on recommendations(user_id, score desc);
create index if not exists applications_user_opp on applications(user_id, opportunity_id);
