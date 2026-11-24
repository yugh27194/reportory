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
    """이번 주 월요일~일요일(일요일 21:00 실행 기준)."""
    start = today - timedelta(days=today.weekday())
    return start, start + timedelta(days=6)


def previous_month(today: date) -> tuple[date, date]:
    first_this = today.replace(day=1)
    end = first_this - timedelta(days=1)
    return end.replace(day=1), end


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
async def cron(task: str, db: SystemDB = Depends(get_system_db)):
    if task == "requeue_stuck_jobs":
        return {"task": task, "requeued": await requeue_stuck_jobs()}
    if task == "weekly_summary":
        start, end = week_range(today_kst())
        return {"task": task, "users": await _enqueue_summaries(db, "week", start, end)}
    if task == "monthly_summary":
        start, end = previous_month(today_kst())
        return {"task": task, "users": await _enqueue_summaries(db, "month", start, end)}
    if task == "evidence_expiry":
        return {"task": task, "notified": await _evidence_expiry(db)}
    # 공고 수집·추천·지원 알림은 Phase 3에서 추가한다.
    raise not_found("알 수 없는 정기 작업이다.")
