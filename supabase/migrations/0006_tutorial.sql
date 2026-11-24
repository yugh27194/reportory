-- 0006_tutorial.sql: 첫 사용 안내(튜토리얼)를 마쳤거나 건너뛴 시각. 비어 있으면 앱에 들어올 때 안내를 띄운다.
alter table profiles add column if not exists tutorial_completed_at timestamptz;
