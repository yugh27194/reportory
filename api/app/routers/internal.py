"""Supabase Cron 전용 내부 엔드포인트(인계서 13.2절). X-Cron-Secret으로만 호출한다."""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends

from app.auth import require_cron_secret
from app.db import SystemDB, get_system_db
from app.errors import not_found
from app.services.jobs import enqueue
from app.worker import requeue_stuck_jobs

router = APIRouter(tags=["internal"], dependencies=[Depends(require_cron_secret)])
KST = ZoneInfo("Asia/Seoul")


def today_kst() -> date:
    return datetime.now(KST).date()


def week_range(today: date) -> tuple[date, date]:
    """이번 주 월요일~일요일(일요일 밤 실행 기준)."""
    start = today - timedelta(days=today.weekday())
    return start, start + timedelta(days=6)


def month_range(today: date) -> tuple[date, date]:
    """이번 달 1일~말일(월 마지막 날 밤 실행 기준)."""
    first_next = (today.replace(day=28) + timedelta(days=4)).replace(day=1)
    return today.replace(day=1), first_next - timedelta(days=1)


def is_last_day_of_month(today: date) -> bool:
    return (today + timedelta(days=1)).day == 1


async def _enqueue_summaries(db: SystemDB, period: str, start: date, end: date) -> int:
    users = await db.all(
        """select distinct user_id from entries
           where entry_date between :s and :e and summary is not null""",
        s=start,
        e=end,
    )
    for u in users:
        await enqueue(
            db,
            "period_summary",
            {"period": period, "period_start": start.isoformat(), "period_end": end.isoformat()},
            user_id=u["user_id"],
        )
    return len(users)


async def _evidence_expiry(db: SystemDB) -> int:
    return await db.execute(
        """insert into notifications (user_id, type, title, link, ref_id)
           select e.user_id, 'evidence_expiry',
                  coalesce(i.title, e.file_name) || ' 증빙이 '
                    || to_char(e.expires_on, 'YYYY-MM-DD') || '에 만료된다.',
                  case when e.item_id is null then '/portfolio' else '/portfolio/' || e.item_id end,
                  e.id
           from evidence e left join items i on i.id = e.item_id
           where e.expires_on between :today and :limit
           on conflict do nothing""",
        today=today_kst(),
        limit=today_kst() + timedelta(days=30),
    )


@router.post("/internal/cron/{task}")
async def cron(task: str, force: bool = False, db: SystemDB = Depends(get_system_db)):
    if task == "requeue_stuck_jobs":
        return {"task": task, "requeued": await requeue_stuck_jobs()}
    if task == "daily_summary":
        today = today_kst()
        return {"task": task, "users": await _enqueue_summaries(db, "day", today, today)}
    if task == "weekly_summary":
        start, end = week_range(today_kst())
        return {"task": task, "users": await _enqueue_summaries(db, "week", start, end)}
    if task == "monthly_summary":
        # Cron은 매일 밤 부르고, 월 마지막 날에만 실행한다(cron 식으로 '말일'을 쓸 수 없다).
        today = today_kst()
        if not (is_last_day_of_month(today) or force):
            return {"task": task, "skipped": "not_last_day_of_month"}
        start, end = month_range(today)
        return {"task": task, "users": await _enqueue_summaries(db, "month", start, end)}
    if task == "evidence_expiry":
        return {"task": task, "notified": await _evidence_expiry(db)}
    if task == "collect_opportunities":
        return {"task": task, **await _enqueue_system_once(db, "collect_opportunities")}
    if task == "score_recommendations":
        return {"task": task, "users": await _enqueue_scoring(db)}
    if task == "application_auto_transitions":
        return {"task": task, "changed": await _auto_transitions(db)}
    if task == "result_reminders":
        return {"task": task, **await _result_reminders(db)}
    raise not_found("알 수 없는 정기 작업이다.")


async def _enqueue_system_once(db: SystemDB, job_type: str) -> dict:
    """사용자 없는 작업을 넣는다. 이미 대기·실행 중이면 또 넣지 않는다."""
    busy = await db.scalar(
        """select 1 from jobs where user_id is null and type = :t
             and status in ('queued', 'running') limit 1""",
        t=job_type,
    )
    if busy:
        return {"skipped": "already_queued"}
    return {"job_id": await enqueue(db, job_type, {})}


async def _enqueue_scoring(db: SystemDB) -> int:
    """항목이 있거나 관심 분야를 정한 사용자마다 추천 계산을 넣는다."""
    users = await db.all(
        """select p.id as user_id from profiles p
           where (exists (select 1 from items i where i.user_id = p.id and i.status = 'approved')
                  or cardinality(p.interests) > 0 or cardinality(p.target_roles) > 0)
             and not exists (select 1 from jobs j where j.user_id = p.id
                             and j.type = 'score_recommendations'
                             and j.status in ('queued', 'running'))"""
    )
    for u in users:
        await enqueue(db, "score_recommendations", {}, user_id=u["user_id"])
    return len(users)


async def _auto_transitions(db: SystemDB) -> int:
    from app.db import UserDB
    from app.services.applications import auto_transitions

    users = await db.all(
        """select distinct user_id from applications
           where status in ('applied', 'accepted')"""
    )
    n = 0
    for u in users:
        n += await auto_transitions(UserDB(db.conn, u["user_id"]), today_kst())
    return n


async def _result_reminders(db: SystemDB) -> dict:
    """발표일(없으면 마감 + 14일)이 지난 결과 대기 지원에 3일 간격으로 최대 3번, 마감 3일 전 알림 1번."""
    today = today_kst()
    results = await db.execute(
        """insert into notifications (user_id, type, title, link, ref_id)
           select a.user_id,
                  'result_reminder_' || least(3, (:today - d.due) / 3 + 1),
                  a.title || ' 결과가 나왔나요? 합격·불합격을 기록해 두면 추천이 더 정확해진다.',
                  '/applications?open=' || a.id, a.id
           from applications a
           cross join lateral (select coalesce(a.result_announce_on, a.apply_deadline + 14) as due) d
           where a.status in ('applied', 'awaiting_result') and d.due is not null
             and d.due <= :today and (:today - d.due) % 3 = 0 and (:today - d.due) <= 6
           on conflict do nothing""",
        today=today,
    )
    deadlines = await db.execute(
        """insert into notifications (user_id, type, title, link, ref_id)
           select user_id, 'apply_deadline',
                  title || ' 마감이 ' || to_char(apply_deadline, 'MM월 DD일') || '이다.',
                  '/applications?open=' || id, id
           from applications
           where status = 'interested' and apply_deadline between :today and :soon
           on conflict do nothing""",
        today=today,
        soon=today + timedelta(days=3),
    )
    return {"result_reminders": results, "deadline_reminders": deadlines}
