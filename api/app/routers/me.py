"""현재 사용자와 프로필(인계서 9.2절 /me)."""

import re
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, field_validator

from app.db import UserDB, as_json, get_user_db
from app.errors import ApiError

router = APIRouter(tags=["me"])

PROFILE_COLUMNS = """id, handle, display_name, display_name_en, headline, email_public, links, goal,
  interests, target_roles, school, major, grade, region, public_profile_enabled,
  llm_consent_at, onboarding_completed_at, tutorial_completed_at, notify_email, created_at, updated_at"""


async def ensure_profile(db: UserDB) -> dict:
    """첫 요청 때 프로필 행을 만든다(auth.users 1:1)."""
    await db.execute("insert into profiles (id) values (:user_id) on conflict (id) do nothing")
    return await db.one(f"select {PROFILE_COLUMNS} from profiles where id = :user_id")


@router.get("/me")
async def get_me(db: UserDB = Depends(get_user_db)):
    return {"user_id": db.user_id, "profile": await ensure_profile(db)}


class Link(BaseModel):
    label: str = Field(min_length=1, max_length=50)
    url: str = Field(pattern=r"^https?://", max_length=500)


class ProfilePatch(BaseModel):
    handle: str | None = None
    display_name: str | None = Field(default=None, max_length=100)
    display_name_en: str | None = Field(default=None, max_length=100)
    headline: str | None = Field(default=None, max_length=120)
    email_public: str | None = Field(default=None, max_length=200)
    links: list[Link] | None = None
    goal: Literal["grad_school", "employment", "undecided"] | None = None
    interests: list[str] | None = None
    target_roles: list[str] | None = None
    school: str | None = None
    major: str | None = None
    grade: int | None = Field(default=None, ge=1, le=6)
    region: str | None = None
    public_profile_enabled: bool | None = None
    notify_email: bool | None = None

    @field_validator("handle")
    @classmethod
    def _handle(cls, v: str | None) -> str | None:
        if v is not None and not re.fullmatch(r"[a-z0-9_-]{3,30}", v):
            raise ValueError("handle은 영문 소문자, 숫자, _, - 3~30자다.")
        return v


@router.patch("/me/profile")
async def patch_profile(body: ProfilePatch, db: UserDB = Depends(get_user_db)):
    await ensure_profile(db)
    values = body.model_dump(exclude_unset=True)
    if values.get("public_profile_enabled"):
        current = await db.scalar("select handle from profiles where id = :user_id")
        if not (values.get("handle") or current):
            raise ApiError(
                422, "validation_error", "공개 프로필을 켜려면 handle을 먼저 정해야 한다."
            )
    if "handle" in values and values["handle"]:
        taken = await db.system.scalar(
            "select 1 from profiles where handle = :h and id <> :uid",
            h=values["handle"],
            uid=db.user_id,
        )
        if taken:
            raise ApiError(409, "handle_taken", "이미 쓰이는 handle이다.")
    sets, params = [], {}
    for key, value in values.items():
        if key == "links":
            sets.append("links = cast(:links as jsonb)")
            params["links"] = as_json(value)
        elif key == "goal":
            sets.append("goal = cast(:goal as goal_type)")
            params["goal"] = value
        else:
            sets.append(f"{key} = :{key}")
            params[key] = value
    if sets:
        await db.execute(f"update profiles set {', '.join(sets)} where id = :user_id", **params)
    return await ensure_profile(db)


@router.post("/me/consent")
async def consent(db: UserDB = Depends(get_user_db)):
    await ensure_profile(db)
    await db.execute(
        "update profiles set llm_consent_at = coalesce(llm_consent_at, now()) where id = :user_id"
    )
    return await ensure_profile(db)


class TutorialIn(BaseModel):
    completed: bool = True


@router.post("/me/tutorial")
async def tutorial(body: TutorialIn, db: UserDB = Depends(get_user_db)):
    """튜토리얼을 마쳤거나 건너뛰면 completed=true, 다시 보려면 false."""
    await ensure_profile(db)
    await db.execute(
        """update profiles set tutorial_completed_at = case when :done then now() else null end
           where id = :user_id""",
        done=body.completed,
    )
    return await ensure_profile(db)


@router.post("/me/onboarding/complete")
async def onboarding_complete(db: UserDB = Depends(get_user_db)):
    await ensure_profile(db)
    await db.execute(
        """update profiles set onboarding_completed_at = coalesce(onboarding_completed_at, now())
           where id = :user_id"""
    )
    return await ensure_profile(db)


@router.get("/me/stats")
async def stats(db: UserDB = Depends(get_user_db)):
    """홈 화면 숫자: 유형별 승인 항목, 검토 대기, 일기 수, 최근 항목, 최근 요약."""
    by_type = await db.all(
        """select type, count(*) as n from items
           where user_id = :user_id and status = 'approved' group by type"""
    )
    entries = await db.one(
        """select count(*) as total,
                  count(*) filter (where entry_date >= current_date - 6) as this_week,
                  count(distinct entry_date) filter (where entry_date >= current_date - 29)
                    as days_this_month
           from entries where user_id = :user_id"""
    )
    recent = await db.all(
        """select id, type, title, organization, approved_at from items
           where user_id = :user_id and status = 'approved'
           order by approved_at desc nulls last limit 5"""
    )
    summary = await db.one(
        """select id, period, period_start, period_end, summary_md from period_summaries
           where user_id = :user_id order by created_at desc limit 1"""
    )
    return {
        "items_by_type": {r["type"]: r["n"] for r in by_type},
        "items_total": sum(r["n"] for r in by_type),
        "pending_proposals": await db.scalar(
            "select count(*) from proposals where user_id = :user_id and status = 'pending'"
        ),
        "open_followups": await db.scalar(
            "select count(*) from followup_questions where user_id = :user_id and status = 'open'"
        ),
        "entries": entries,
        "documents": await db.scalar("select count(*) from documents where user_id = :user_id"),
        "evidence": await db.scalar("select count(*) from evidence where user_id = :user_id"),
        "recent_items": recent,
        "latest_summary": summary,
    }
