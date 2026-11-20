"""일기(인계서 9.2절 /entries, 11.1절)."""

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.config import Settings, get_settings
from app.db import UserDB, get_user_db
from app.errors import ApiError, not_found
from app.routers.me import ensure_profile
from app.services.jobs import check_daily_limit, enqueue
from app.services.proposals import reject_pending_for_entry

router = APIRouter(tags=["entries"])

ENTRY_COLUMNS = "id, entry_date, body, extraction_status, extracted_at, created_at, updated_at"


class EntryIn(BaseModel):
    entry_date: date
    body: str = Field(min_length=1, max_length=20000)


class EntryPatch(BaseModel):
    entry_date: date | None = None
    body: str | None = Field(default=None, min_length=1, max_length=20000)


async def _start_extraction(db: UserDB, entry_id: UUID, settings: Settings) -> UUID:
    profile = await ensure_profile(db)
    if profile["llm_consent_at"] is None:
        raise ApiError(
            403, "consent_required", "일기 분석을 쓰려면 먼저 외부 LLM 처리에 동의해야 한다."
        )
    await check_daily_limit(db, ["extract_entry"], settings.daily_limit_extract)
    await db.execute(
        "update entries set extraction_status = 'queued' where id = :id and user_id = :user_id",
        id=entry_id,
    )
    return await enqueue(db, "extract_entry", {"entry_id": str(entry_id)})


async def _get(db: UserDB, entry_id: UUID) -> dict:
    row = await db.one(
        f"select {ENTRY_COLUMNS} from entries where id = :id and user_id = :user_id", id=entry_id
    )
    if row is None:
        raise not_found("일기를 찾을 수 없다.")
    return row


@router.post("/entries", status_code=202)
async def create_entry(
    body: EntryIn, db: UserDB = Depends(get_user_db), settings: Settings = Depends(get_settings)
):
    profile = await ensure_profile(db)
    entry = await db.one(
        f"""insert into entries (user_id, entry_date, body) values (:user_id, :d, :body)
            returning {ENTRY_COLUMNS}""",
        d=body.entry_date,
        body=body.body,
    )
    job_id = None
    if profile["llm_consent_at"] is not None:
        job_id = await _start_extraction(db, entry["id"], settings)
        entry["extraction_status"] = "queued"
    return {"entry": entry, "job_id": job_id}


@router.get("/entries")
async def list_entries(
    db: UserDB = Depends(get_user_db),
    from_: date | None = Query(default=None, alias="from"),
    to: date | None = None,
):
    return {
        "entries": await db.all(
            f"""select {ENTRY_COLUMNS} from entries where user_id = :user_id
              and (cast(:f as date) is null or entry_date >= :f)
              and (cast(:t as date) is null or entry_date <= :t)
            order by entry_date desc, created_at desc limit 500""",
            f=from_,
            t=to,
        )
    }


@router.get("/entries/{entry_id}")
async def get_entry(entry_id: UUID, db: UserDB = Depends(get_user_db)):
    entry = await _get(db, entry_id)
    entry["proposals"] = await db.all(
        """select id, kind, status, payload, item_id, confidence, quote, created_at
           from proposals where user_id = :user_id and entry_id = :id order by created_at""",
        id=entry_id,
    )
    entry["sources"] = await db.all(
        """select s.id, s.item_id, s.quote, i.title as item_title, i.type as item_type,
                  i.status as item_status
           from item_sources s join items i on i.id = s.item_id
           where s.user_id = :user_id and s.entry_id = :id order by s.created_at""",
        id=entry_id,
    )
    entry["job"] = await db.one(
        """select id, status from jobs where user_id = :user_id and type = 'extract_entry'
             and payload ->> 'entry_id' = cast(:eid as text)
           order by created_at desc limit 1""",
        eid=str(entry_id),
    )
    return entry


@router.patch("/entries/{entry_id}")
async def patch_entry(entry_id: UUID, body: EntryPatch, db: UserDB = Depends(get_user_db)):
    await _get(db, entry_id)
    values = body.model_dump(exclude_unset=True, exclude_none=True)
    if values:
        sets = ", ".join(f"{k} = :{k}" for k in values)
        await db.execute(
            f"update entries set {sets} where id = :id and user_id = :user_id",
            id=entry_id,
            **values,
        )
    return await _get(db, entry_id)


@router.post("/entries/{entry_id}/reextract", status_code=202)
async def reextract(
    entry_id: UUID, db: UserDB = Depends(get_user_db), settings: Settings = Depends(get_settings)
):
    await _get(db, entry_id)
    await reject_pending_for_entry(db, entry_id)
    return {"job_id": await _start_extraction(db, entry_id, settings)}


@router.delete("/entries/{entry_id}", status_code=204)
async def delete_entry(entry_id: UUID, db: UserDB = Depends(get_user_db)):
    await _get(db, entry_id)
    # 대기 제안이 만든 제안 상태 항목은 거절하고, 승인된 항목은 남긴다(근거 행은 cascade로 지워진다).
    await reject_pending_for_entry(db, entry_id)
    await db.execute("delete from entries where id = :id and user_id = :user_id", id=entry_id)
