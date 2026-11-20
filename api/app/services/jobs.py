"""작업 큐 등록과 사용량 제한(인계서 9.1절, 13.1절)."""

from typing import Any
from uuid import UUID

from app.db import SystemDB, UserDB, as_json
from app.errors import rate_limited


async def enqueue(
    db: SystemDB | UserDB, job_type: str, payload: dict[str, Any], user_id: UUID | None = None
) -> UUID:
    if isinstance(db, UserDB):
        return await db.scalar(
            """insert into jobs (user_id, type, payload)
               values (:user_id, :type, cast(:payload as jsonb)) returning id""",
            type=job_type,
            payload=as_json(payload),
        )
    return await db.scalar(
        """insert into jobs (user_id, type, payload)
           values (:uid, :type, cast(:payload as jsonb)) returning id""",
        uid=user_id,
        type=job_type,
        payload=as_json(payload),
    )


async def check_daily_limit(db: UserDB, job_types: list[str], limit: int) -> None:
    """한국 시간 기준 오늘 등록한 작업 수가 limit 이상이면 429를 던진다."""
    used = await db.scalar(
        """select count(*) from jobs
           where user_id = :user_id and type = any(:types)
             and created_at >= date_trunc('day', now() at time zone 'Asia/Seoul')
                                at time zone 'Asia/Seoul'""",
        types=job_types,
    )
    if used >= limit:
        raise rate_limited()
