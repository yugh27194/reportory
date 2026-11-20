"""공개 프로필(인계서 9.2절 /public/{handle}, 11.9절). 인증이 필요 없다.

RLS 익명 접근으로 열지 않고, 서버가 공개 조건을 확인한 데이터만 돌려준다.
"""

from fastapi import APIRouter, Depends

from app.db import SystemDB, get_system_db
from app.errors import not_found

router = APIRouter(tags=["public"])


@router.get("/public/{handle}")
async def public_profile(handle: str, db: SystemDB = Depends(get_system_db)):
    profile = await db.one(
        """select id, handle, display_name, display_name_en, email_public, links, school, major,
                  updated_at
           from profiles where handle = :handle and public_profile_enabled""",
        handle=handle,
    )
    if profile is None:
        raise not_found("공개 프로필을 찾을 수 없다.")
    items = await db.all(
        """select i.id, i.type, i.title, i.title_en, i.organization, i.role, i.start_date,
                  i.end_date, i.is_ongoing, i.summary, i.details, i.metrics, i.links, i.updated_at,
                  coalesce((select jsonb_agg(s.name order by s.name) from item_skills isk
                    join skills s on s.id = isk.skill_id
                    where isk.item_id = i.id and isk.user_id = i.user_id), '[]'::jsonb) as skills
           from items i
           where i.user_id = :uid and i.status = 'approved' and i.visibility = 'public'
           order by coalesce(i.end_date, i.start_date, i.created_at::date) desc""",
        uid=profile["id"],
    )
    last_updated = max([profile["updated_at"], *[i["updated_at"] for i in items]])
    profile.pop("id")
    profile.pop("updated_at")
    for i in items:
        i.pop("updated_at")
    return {"profile": profile, "items": items, "last_updated": last_updated}
