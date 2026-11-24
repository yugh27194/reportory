-- 0004_growth.sql: 스펙 레이더의 목표 기준선. {"preset": "...", "values": {"experience": 1, ...}}
alter table profiles add column if not exists spec_target jsonb;
