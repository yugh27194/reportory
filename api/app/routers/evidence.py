"""증빙(인계서 9.2절 /evidence, 11.7절)."""

import uuid
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile
from pydantic import BaseModel

from app.config import Settings, get_settings
from app.db import UserDB, get_user_db
from app.errors import not_found
from app.routers.me import ensure_profile
from app.services.items import add_source, get_item
from app.services.jobs import enqueue
from app.storage import get_storage
from app.uploads import MIME_EXT, check_upload

router = APIRouter(tags=["evidence"])

EVIDENCE_MIME = {"application/pdf", "image/png", "image/jpeg", "image/webp"}
EVIDENCE_COLUMNS = """id, item_id, kind, status, file_name, mime_type, size_bytes, extracted,
  issued_on, expires_on, visibility, created_at"""


async def _get(db: UserDB, evidence_id: UUID) -> dict:
    row = await db.one(
        f"select {EVIDENCE_COLUMNS}, storage_path from evidence where id = :id and user_id = :user_id",
        id=evidence_id,
    )
    if row is None:
        raise not_found("증빙을 찾을 수 없다.")
    return row


@router.post("/evidence", status_code=202)
async def upload(
    file: UploadFile = File(...),
    item_id: UUID | None = Form(default=None),
    db: UserDB = Depends(get_user_db),
):
    data = await file.read()
    mime = check_upload(data, EVIDENCE_MIME)
    if item_id:
        await get_item(db, item_id, statuses=("approved", "proposed"))
    await ensure_profile(db)
    path = f"{db.user_id}/{uuid.uuid4()}.{MIME_EXT[mime]}"
    await get_storage().put("evidence", path, data, mime)
    row = await db.one(
        f"""insert into evidence (user_id, item_id, storage_path, file_name, mime_type, size_bytes)
            values (:user_id, :item_id, :path, :name, :mime, :size)
            returning {EVIDENCE_COLUMNS}""",
        item_id=item_id,
        path=path,
        name=(file.filename or "evidence")[:200],
        mime=mime,
        size=len(data),
    )
    job_id = await enqueue(db, "process_evidence", {"evidence_id": str(row["id"])})
    return {"evidence": row, "job_id": job_id}


@router.get("/evidence")
async def list_evidence(item_id: UUID | None = None, db: UserDB = Depends(get_user_db)):
    rows = await db.all(
        f"""select {EVIDENCE_COLUMNS} from evidence where user_id = :user_id
              and (cast(:item_id as uuid) is null or item_id = :item_id)
            order by created_at desc limit 500""",
        item_id=item_id,
    )
    return {"evidence": rows}


@router.get("/evidence/{evidence_id}/url")
async def signed_url(
    evidence_id: UUID,
    download: bool = False,
    db: UserDB = Depends(get_user_db),
    settings: Settings = Depends(get_settings),
):
    row = await _get(db, evidence_id)
    ttl = settings.signed_url_ttl_seconds
    url = await get_storage().signed_url(
        "evidence", row["storage_path"], ttl, download_name=row["file_name"] if download else None
    )
    return {"url": url, "expires_in": ttl}


class EvidencePatch(BaseModel):
    item_id: UUID | None = None
    visibility: Literal["private", "public"] | None = None


@router.patch("/evidence/{evidence_id}")
async def patch_evidence(evidence_id: UUID, body: EvidencePatch, db: UserDB = Depends(get_user_db)):
    await _get(db, evidence_id)
    values = body.model_dump(exclude_unset=True)
    if "item_id" in values:
        if values["item_id"]:
            await get_item(db, values["item_id"], statuses=("approved", "proposed"))
        await db.execute(
            "update evidence set item_id = :item_id where id = :id and user_id = :user_id",
            id=evidence_id,
            item_id=values["item_id"],
        )
        if values["item_id"]:
            await add_source(db, values["item_id"], evidence_id=evidence_id)
    if values.get("visibility"):
        await db.execute(
            """update evidence set visibility = cast(:v as visibility)
               where id = :id and user_id = :user_id""",
            id=evidence_id,
            v=values["visibility"],
        )
    row = await _get(db, evidence_id)
    row.pop("storage_path")
    return row


@router.delete("/evidence/{evidence_id}", status_code=204)
async def delete_evidence(evidence_id: UUID, db: UserDB = Depends(get_user_db)):
    row = await _get(db, evidence_id)
    await db.execute("delete from evidence where id = :id and user_id = :user_id", id=evidence_id)
    await get_storage().delete("evidence", [row["storage_path"]])
