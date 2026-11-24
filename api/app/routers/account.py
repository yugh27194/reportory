"""알림, 요약, 내보내기, 계정 삭제(인계서 9.2절)."""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.db import UserDB, get_user_db
from app.errors import ApiError, not_found
from app.jobs.account import EXPORT_TTL_SECONDS, export_url
from app.services.jobs import enqueue

router = APIRouter(tags=["account"])


@router.get("/notifications")
async def notifications(db: UserDB = Depends(get_user_db)):
    rows = await db.all(
        """select id, type, title, body, link, read_at, created_at from notifications
           where user_id = :user_id order by created_at desc limit 50"""
    )
    unread = await db.scalar(
        "select count(*) from notifications where user_id = :user_id and read_at is null"
    )
    return {"notifications": rows, "unread": unread}


class ReadIn(BaseModel):
    ids: list[UUID] | None = Field(default=None, max_length=200)  # 비우면 모두 읽음


@router.post("/notifications/read")
async def mark_read(body: ReadIn, db: UserDB = Depends(get_user_db)):
    n = await db.execute(
        """update notifications set read_at = now()
           where user_id = :user_id and read_at is null
             and (cast(:ids as uuid[]) is null or id = any(:ids))""",
        ids=body.ids,
    )
    return {"updated": n}


@router.get("/summaries")
async def summaries(period: Literal["week", "month"] = "week", db: UserDB = Depends(get_user_db)):
    rows = await db.all(
        """select id, period, period_start, period_end, summary_md, highlights, created_at
           from period_summaries where user_id = :user_id and period = cast(:p as period_type)
           order by period_start desc limit 52""",
        p=period,
    )
    return {"summaries": rows}


@router.post("/export", status_code=202)
async def export(db: UserDB = Depends(get_user_db)):
    running = await db.scalar(
        """select count(*) from jobs where user_id = :user_id and type = 'export_data'
             and status in ('queued', 'running')"""
    )
    if running:
        raise ApiError(409, "already_running", "이미 내보내기를 준비하고 있다.")
    return {"job_id": await enqueue(db, "export_data", {})}


@router.get("/export/{job_id}/url")
async def export_download(job_id: UUID, db: UserDB = Depends(get_user_db)):
    url = await export_url(db, job_id)
    if url is None:
        raise not_found("내보내기 파일을 찾을 수 없다.")
    return {"url": url, "expires_in": EXPORT_TTL_SECONDS}


@router.get("/export/latest")
async def export_latest(db: UserDB = Depends(get_user_db)):
    row = await db.one(
        """select id, status, created_at, updated_at from jobs
           where user_id = :user_id and type = 'export_data'
           order by created_at desc limit 1"""
    )
    return {"job": row}


class DeleteIn(BaseModel):
    confirm: str


@router.delete("/account", status_code=202)
async def delete_account(body: DeleteIn, db: UserDB = Depends(get_user_db)):
    if body.confirm != "계정 삭제":
        raise ApiError(422, "validation_error", "확인 문구로 '계정 삭제'를 정확히 입력해야 한다.")
    return {"job_id": await enqueue(db, "delete_account", {})}
