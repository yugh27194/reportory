"""공개 프로필(인계서 9.2절 /public/{handle}, 11.9절). 인증이 필요 없다.

RLS 익명 접근으로 열지 않고, 서버가 공개 조건을 확인한 데이터만 돌려준다.
"""

from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse

from app.config import Settings, get_settings
from app.db import SystemDB, get_system_db
from app.errors import not_found
from app.storage import get_storage

router = APIRouter(tags=["public"])


async def _profile(db: SystemDB, handle: str) -> dict:
    profile = await db.one(
        """select id, handle, display_name, display_name_en, headline, email_public, links,
                  school, major, updated_at
           from profiles where handle = :handle and public_profile_enabled""",
        handle=handle,
    )
    if profile is None:
        raise not_found("공개 프로필을 찾을 수 없다.")
    return profile


@router.get("/public/{handle}")
async def public_profile(handle: str, db: SystemDB = Depends(get_system_db)):
    profile = await _profile(db, handle)
    items = await db.all(
        """select i.id, i.type, i.title, i.title_en, i.organization, i.role, i.start_date,
                  i.end_date, i.is_ongoing, i.summary, i.details, i.metrics, i.links, i.updated_at,
                  coalesce((select jsonb_agg(s.name order by s.name) from item_skills isk
                    join skills s on s.id = isk.skill_id
                    where isk.item_id = i.id and isk.user_id = i.user_id), '[]'::jsonb) as skills,
                  coalesce((select jsonb_agg(jsonb_build_object('id', e.id, 'kind', e.kind,
                      'file_name', e.file_name) order by e.created_at)
                    from evidence e where e.item_id = i.id and e.user_id = i.user_id
                      and e.visibility = 'public'), '[]'::jsonb) as evidence
           from items i
           where i.user_id = :uid and i.status = 'approved' and i.visibility = 'public'
           order by coalesce(i.end_date, i.start_date, i.created_at::date) desc""",
        uid=profile["id"],
    )
    documents = await db.all(
        """select d.id, d.title, d.format, d.language, v.created_at as version_at
           from documents d
           join lateral (select created_at from document_versions dv
                         where dv.document_id = d.id and dv.status = 'succeeded'
                           and dv.pdf_path is not null
                         order by version desc limit 1) v on true
           where d.user_id = :uid and d.is_public
           order by v.created_at desc""",
        uid=profile["id"],
    )
    last_updated = max([profile["updated_at"], *[i["updated_at"] for i in items]])
    profile.pop("id")
    profile.pop("updated_at")
    for i in items:
        i.pop("updated_at")
    return {
        "profile": profile,
        "items": items,
        "documents": documents,
        "last_updated": last_updated,
    }


@router.get("/public/{handle}/evidence/{evidence_id}")
async def public_evidence(
    handle: str,
    evidence_id: UUID,
    db: SystemDB = Depends(get_system_db),
    settings: Settings = Depends(get_settings),
):
    profile = await _profile(db, handle)
    row = await db.one(
        """select e.storage_path from evidence e join items i on i.id = e.item_id
           where e.id = :id and e.user_id = :uid and e.visibility = 'public'
             and i.status = 'approved' and i.visibility = 'public'""",
        id=evidence_id,
        uid=profile["id"],
    )
    if row is None:
        raise not_found("공개 증빙을 찾을 수 없다.")
    url = await get_storage().signed_url(
        "evidence", row["storage_path"], settings.signed_url_ttl_seconds
    )
    return RedirectResponse(url, status_code=302)


@router.get("/public/{handle}/documents/{document_id}")
async def public_document(
    handle: str,
    document_id: UUID,
    db: SystemDB = Depends(get_system_db),
    settings: Settings = Depends(get_settings),
):
    profile = await _profile(db, handle)
    row = await db.one(
        """select v.pdf_path, d.title from documents d
           join document_versions v on v.document_id = d.id
           where d.id = :id and d.user_id = :uid and d.is_public and v.status = 'succeeded'
             and v.pdf_path is not null
           order by v.version desc limit 1""",
        id=document_id,
        uid=profile["id"],
    )
    if row is None:
        raise not_found("공개 문서를 찾을 수 없다.")
    url = await get_storage().signed_url(
        "documents", row["pdf_path"], settings.signed_url_ttl_seconds
    )
    return RedirectResponse(url, status_code=302)
