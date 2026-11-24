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
  llm_consent_at, onboarding_completed_at, notify_email, created_at, updated_at"""


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
