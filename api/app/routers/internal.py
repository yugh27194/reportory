"""Supabase Cron 전용 내부 엔드포인트(인계서 13.2절). X-Cron-Secret으로만 호출한다."""

from fastapi import APIRouter, Depends

from app.auth import require_cron_secret
from app.errors import not_found
from app.worker import requeue_stuck_jobs

router = APIRouter(tags=["internal"], dependencies=[Depends(require_cron_secret)])


@router.post("/internal/cron/{task}")
async def cron(task: str):
    if task == "requeue_stuck_jobs":
        return {"task": task, "requeued": await requeue_stuck_jobs()}
    # 나머지 정기 작업은 해당 Phase에서 추가한다.
    raise not_found("알 수 없는 정기 작업이다.")
