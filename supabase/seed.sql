-- 개발용 샘플 일기. 로컬에서 dev@example.com으로 한 번 로그인한 뒤 `supabase db reset` 또는
-- psql로 다시 실행하면, 그 사용자에게 샘플 일기가 들어간다. 사용자가 없으면 아무것도 넣지 않는다.
insert into entries (user_id, entry_date, body)
select u.id, d.entry_date, d.body
from auth.users u
cross join (values
  (date '2026-11-10', '오늘 OO 해커톤에서 팀원 3명과 FastAPI로 백엔드를 맡았다. 결과 발표에서 우수상을 받았다.'),
  (date '2026-11-12', '딥러닝 프로젝트 모델 학습 다시 돌림. 검증 정확도가 0.71에서 0.78로 올랐다.'),
  (date '2026-11-14', '비 와서 하루 종일 집에 있었다.')
) as d(entry_date, body)
where u.email = 'dev@example.com'
  and not exists (select 1 from entries e where e.user_id = u.id);
