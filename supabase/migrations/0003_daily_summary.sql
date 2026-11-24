-- 0003_daily_summary.sql: 요약을 하루(밤) · 주(일요일 밤) · 월(마지막 날 밤) 세 단위로 만든다.
alter type period_type add value if not exists 'day';
