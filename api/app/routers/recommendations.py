"""활동 추천과 공고(인계서 9.2절 /recommendations, /opportunities, 11.4절)."""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.config import Settings, get_settings
from app.crawler.fetch import FetchError, check_url
from app.db import UserDB, get_user_db
from app.errors import ApiError, not_found
from app.routers.me import ensure_profile
from app.services.applications import create_application, transition
from app.services.jobs import check_daily_limit, enqueue

router = APIRouter(tags=["recommendations"])


@router.get("/recommendations")
async def list_recommendations(db: UserDB = Depends(get_user_db)):
    rows = await db.all(
        """select r.id, r.score, r.score_breakdown, r.reason, r.feedback, r.generated_at,
                  o.id as opportunity_id, o.title, o.organizer, o.category, o.summary,
                  o.source_url, o.source_site, o.apply_deadline, o.activity_start, o.activity_end,
                  o.benefits, o.location, o.is_online, o.tags, o.eligibility,
                  (o.created_by is not null) as added_by_me,
                  coalesce((select json_agg(json_build_object('id', i.id, 'title', i.title,
                                                              'type', i.type))
                            from items i
                            where i.user_id = :user_id and i.status = 'approved'
                              and i.id = any(r.reason_item_ids)), '[]') as reason_items
           from recommendations r join opportunities o on o.id = r.opportunity_id
           where r.user_id = :user_id and o.is_active
             and (r.feedback is null or r.feedback = 'interested')
             and (o.apply_deadline is null or o.apply_deadline >= current_date)
           order by (r.feedback is null) desc, r.score desc
           limit 60"""
    )
    last = await db.one(
        """select status, created_at, last_error from jobs
           where user_id = :user_id and type = 'score_recommendations'
           order by created_at desc limit 1"""
    )
    return {"recommendations": rows, "last_job": last}


class FeedbackIn(BaseModel):
    feedback: Literal["interested", "dismissed", "applied"]


@router.post("/recommendations/{rec_id}/feedback")
async def feedback(rec_id: UUID, body: FeedbackIn, db: UserDB = Depends(get_user_db)):
    rec = await db.one(
        """select r.id, r.feedback, o.id as opportunity_id, o.title, o.organizer, o.category,
                  o.apply_deadline, o.result_announce_on, o.activity_start, o.activity_end
           from recommendations r join opportunities o on o.id = r.opportunity_id
           where r.id = :id and r.user_id = :user_id""",
        id=rec_id,
    )
    if rec is None:
        raise not_found("추천을 찾을 수 없다.")
    await db.execute(
        """update recommendations set feedback = :f, feedback_at = now()
           where id = :id and user_id = :user_id""",
        f=body.feedback,
        id=rec_id,
    )
    application = None
    if body.feedback in ("interested", "applied"):
        existing = await db.one(
            """select id, status from applications
               where user_id = :user_id and opportunity_id = :oid""",
            oid=rec["opportunity_id"],
        )
        if existing is None:
            application = await create_application(db, {**rec, "category": str(rec["category"])})
        else:
            application = existing
        if body.feedback == "applied" and application["status"] == "interested":
            application = await transition(db, application["id"], "applied")
    return {"id": rec_id, "feedback": body.feedback, "application": application}


@router.post("/recommendations/refresh", status_code=202)
async def refresh(db: UserDB = Depends(get_user_db)):
    await ensure_profile(db)
    await check_daily_limit(db, ["score_recommendations"], 10)
    return {"job_id": await enqueue(db, "score_recommendations", {})}


class FromUrlIn(BaseModel):
    url: str = Field(min_length=8, max_length=2000)


@router.post("/opportunities/from-url", status_code=202)
async def from_url(
    body: FromUrlIn,
    db: UserDB = Depends(get_user_db),
    settings: Settings = Depends(get_settings),
):
    profile = await ensure_profile(db)
    if profile["llm_consent_at"] is None:
        raise ApiError(
            403, "consent_required", "공고를 읽으려면 먼저 외부 LLM 처리에 동의해야 한다."
        )
    try:
        url = await check_url(body.url)
    except FetchError as exc:
        raise ApiError(422, "validation_error", str(exc)) from exc
    await check_daily_limit(db, ["fetch_opportunity_url"], settings.daily_limit_url_add)
    return {"job_id": await enqueue(db, "fetch_opportunity_url", {"url": url})}
