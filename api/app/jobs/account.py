"""데이터 내보내기와 계정 삭제(인계서 11.10절)."""

import io
import json
import logging
import zipfile
from datetime import UTC, datetime
from uuid import UUID

import httpx

from app.config import get_settings
from app.db import UserDB
from app.llm.demo import sentences
from app.services.documents import build_content
from app.storage import BUCKETS, get_storage

log = logging.getLogger("reportory.account")

EXPORT_TTL_SECONDS = 24 * 3600

# 테스트에서 Supabase Admin API 대역을 끼우는 자리다.
_transport: httpx.AsyncBaseTransport | None = None


def set_transport(transport: httpx.AsyncBaseTransport | None) -> None:
    global _transport
    _transport = transport


def _dump(data) -> bytes:
    return json.dumps(data, ensure_ascii=False, indent=2, default=str).encode()


async def export_data(db: UserDB, payload: dict) -> dict:
    profile = (
        await db.one(
            """select display_name, display_name_en, headline, email_public, links, goal, interests,
                  target_roles, school, major, grade, region, handle, created_at
           from profiles where id = :user_id"""
        )
        or {}
    )
    items = await db.all(
        """select id, type, status, title, title_en, organization, role, start_date, end_date,
                  is_ongoing, summary, details, metrics, links, visibility, approved_at
           from items where user_id = :user_id and status in ('approved', 'proposed')
           order by type, start_date"""
    )
    for i in items:
        i["skills"] = [
            r["name"]
            for r in await db.all(
                """select s.name from item_skills isk join skills s on s.id = isk.skill_id
               where isk.item_id = :id and isk.user_id = :user_id""",
                id=i["id"],
            )
        ]
        i["sources"] = await db.all(
            """select entry_id, import_id, evidence_id, followup_id, quote, created_at
               from item_sources where item_id = :id and user_id = :user_id""",
            id=i["id"],
        )
    approved = [i for i in items if i["status"] == "approved"]
    lines = {
        str(i["id"]): {"heading": None, "lines": sentences(i["summary"] or "")} for i in approved
    }
    resume = build_content("academic_cv", profile, approved, lines)
    resume["meta"] = {
        "canonical": "https://jsonresume.org/schema",
        "lastModified": datetime.now(UTC).isoformat(),
    }
    entries = await db.all(
        """select id, entry_date, body, summary, created_at from entries
           where user_id = :user_id order by entry_date"""
    )
    applications = await db.all(
        """select a.*, coalesce((select jsonb_agg(to_jsonb(e) - 'user_id' order by e.created_at)
                    from application_events e where e.application_id = a.id), '[]') as events
           from applications a where a.user_id = :user_id order by a.created_at"""
    )
    for a in applications:
        a.pop("user_id", None)
    evidence = await db.all(
        """select id, item_id, kind, file_name, storage_path, issued_on, expires_on, extracted
           from evidence where user_id = :user_id"""
    )

    buf = io.BytesIO()
    storage = get_storage()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("resume.json", _dump(resume))
        z.writestr("profile.json", _dump(profile))
        z.writestr("items.json", _dump(items))
        z.writestr("entries.json", _dump(entries))
        z.writestr("applications.json", _dump(applications))
        z.writestr(
            "evidence.json",
            _dump([{k: v for k, v in e.items() if k != "storage_path"} for e in evidence]),
        )
        for e in evidence:
            try:
                data = await storage.get("evidence", e["storage_path"])
            except Exception:  # noqa: BLE001 - 파일이 없어도 나머지는 내보낸다
                continue
            z.writestr(f"evidence/{e['id']}_{e['file_name']}", data)
    stamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    path = f"{db.user_id}/reportory-export-{stamp}.zip"
    await storage.put("exports", path, buf.getvalue(), "application/zip")
    await db.execute(
        """insert into notifications (user_id, type, title, link)
           values (:user_id, 'export_ready', '데이터 내보내기 파일이 준비됐다.', '/settings')"""
    )
    return {"path": path, "items": len(items), "entries": len(entries), "evidence": len(evidence)}


async def delete_account(db: UserDB, payload: dict) -> dict:
    """Storage의 사용자 폴더를 지운 뒤 사용자를 삭제한다. DB 행은 on delete cascade로 지워진다."""
    storage = get_storage()
    removed = 0
    for bucket in BUCKETS:
        removed += await storage.delete_prefix(bucket, f"{db.user_id}/")
    s = get_settings()
    if s.supabase_url and s.supabase_service_role_key:
        headers = {
            "Authorization": f"Bearer {s.supabase_service_role_key}",
            "apikey": s.supabase_service_role_key,
        }
        async with httpx.AsyncClient(timeout=30.0, transport=_transport) as http:
            resp = await http.delete(
                f"{s.supabase_url.rstrip('/')}/auth/v1/admin/users/{db.user_id}", headers=headers
            )
        if resp.status_code >= 400 and resp.status_code != 404:
            raise RuntimeError(f"Supabase Admin API 오류: HTTP {resp.status_code}")
    else:
        # service role 키가 없으면 DB에서 직접 지운다(로컬 개발, DB 사용자가 auth 스키마에 쓸 수 있을 때).
        await db.system.execute("delete from auth.users where id = :uid", uid=db.user_id)
    log.info("account deleted user=%s files=%s", db.user_id, removed)
    return {"files_removed": removed}


async def export_url(db: UserDB, job_id: UUID) -> str | None:
    row = await db.one(
        """select result from jobs where id = :id and user_id = :user_id
             and type = 'export_data' and status = 'succeeded'""",
        id=job_id,
    )
    if not row or not row["result"]:
        return None
    return await get_storage().signed_url(
        "exports",
        row["result"]["path"],
        EXPORT_TTL_SECONDS,
        download_name=row["result"]["path"].rsplit("/", 1)[-1],
    )
