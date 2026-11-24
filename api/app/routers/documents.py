"""목적별 문서(인계서 9.2절 /documents, 11.5절)."""

from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.config import Settings, get_settings
from app.db import UserDB, as_json, get_user_db
from app.errors import ApiError, not_found, validation_error
from app.routers.me import ensure_profile
from app.services.documents import FORMAT_LABELS, item_types_for, rank_items
from app.services.jobs import check_daily_limit, enqueue
from app.services.render import render_html
from app.services.similarity import safe_embed
from app.storage import get_storage

router = APIRouter(tags=["documents"])

Format = Literal["academic_cv", "resume_en", "resume_ko", "project_portfolio"]
DOC_COLUMNS = "id, format, title, target_description, language, is_public, created_at, updated_at"
VERSION_COLUMNS = (
    "id, version, selected_item_ids, options, status, pdf_path is not null as has_pdf, created_at"
)


class DocumentIn(BaseModel):
    format: Format
    title: str = Field(min_length=1, max_length=120)
    target_description: str | None = Field(default=None, max_length=2000)
    language: Literal["ko", "en"] | None = None


class DocumentPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    target_description: str | None = Field(default=None, max_length=2000)
    is_public: bool | None = None


async def _doc(db: UserDB, document_id: UUID) -> dict:
    row = await db.one(
        f"select {DOC_COLUMNS} from documents where id = :id and user_id = :user_id",
        id=document_id,
    )
    if row is None:
        raise not_found("문서를 찾을 수 없다.")
    return row


@router.get("/documents/formats")
async def formats():
    return {
        "formats": [{"key": k, "label": v} for k, v in FORMAT_LABELS.items() if k != "web_profile"]
    }


@router.post("/documents", status_code=201)
async def create_document(body: DocumentIn, db: UserDB = Depends(get_user_db)):
    await ensure_profile(db)
    language = body.language or ("en" if body.format == "resume_en" else "ko")
    return await db.one(
        f"""insert into documents (user_id, format, title, target_description, language)
            values (:user_id, cast(:format as document_format), :title, :target, :lang)
            returning {DOC_COLUMNS}""",
        format=body.format,
        title=body.title,
        target=body.target_description,
        lang=language,
    )


@router.get("/documents")
async def list_documents(db: UserDB = Depends(get_user_db)):
    rows = await db.all(
        f"""select {", ".join("d." + c.strip() for c in DOC_COLUMNS.split(","))},
                   (select jsonb_build_object('version', v.version, 'status', v.status,
                      'created_at', v.created_at)
                    from document_versions v where v.document_id = d.id
                    order by v.version desc limit 1) as latest
            from documents d where d.user_id = :user_id order by d.updated_at desc"""
    )
    return {"documents": rows}


@router.get("/documents/{document_id}")
async def get_document(document_id: UUID, db: UserDB = Depends(get_user_db)):
    doc = await _doc(db, document_id)
    doc["versions"] = await db.all(
        f"""select {VERSION_COLUMNS} from document_versions
            where document_id = :id and user_id = :user_id order by version desc""",
        id=document_id,
    )
    return doc


@router.patch("/documents/{document_id}")
async def patch_document(document_id: UUID, body: DocumentPatch, db: UserDB = Depends(get_user_db)):
    await _doc(db, document_id)
    values = body.model_dump(exclude_unset=True)
    if values:
        sets = ", ".join(f"{k} = :{k}" for k in values)
        await db.execute(
            f"update documents set {sets} where id = :id and user_id = :user_id",
            id=document_id,
            **values,
        )
    return await _doc(db, document_id)


@router.delete("/documents/{document_id}", status_code=204)
async def delete_document(document_id: UUID, db: UserDB = Depends(get_user_db)):
    await _doc(db, document_id)
    paths = [
        r["pdf_path"]
        for r in await db.all(
            """select pdf_path from document_versions where document_id = :id and user_id = :user_id
             and pdf_path is not null""",
            id=document_id,
        )
    ]
    await db.execute("delete from documents where id = :id and user_id = :user_id", id=document_id)
    await get_storage().delete("documents", paths)


@router.post("/documents/{document_id}/preview-selection")
async def preview_selection(document_id: UUID, db: UserDB = Depends(get_user_db)):
    doc = await _doc(db, document_id)
    vectors = await safe_embed([doc["target_description"]]) if doc["target_description"] else None
    items = await rank_items(db, doc["format"], vectors[0] if vectors else None)
    return {"items": items}


class VersionIn(BaseModel):
    selected_item_ids: list[UUID] = Field(min_length=1, max_length=60)
    options: dict[str, Any] = {}


@router.post("/documents/{document_id}/versions", status_code=202)
async def create_version(
    document_id: UUID,
    body: VersionIn,
    db: UserDB = Depends(get_user_db),
    settings: Settings = Depends(get_settings),
):
    doc = await _doc(db, document_id)
    ids = list(dict.fromkeys(body.selected_item_ids))
    rows = await db.all(
        """select id, type, title, title_en from items
           where user_id = :user_id and status = 'approved' and id = any(:ids)""",
        ids=ids,
    )
    if len(rows) != len(ids):
        raise not_found("고른 항목 중 승인된 항목이 아닌 것이 있다.")
    allowed = item_types_for(doc["format"])
    if any(r["type"] not in allowed for r in rows):
        raise validation_error("이 문서 형식에 넣을 수 없는 유형의 항목이 있다.")
    if doc["format"] == "resume_en":
        # 사람 이름·기관 고유명사의 영문 표기를 지어내지 않도록, 영문 제목이 없으면 먼저 받는다(10.8절).
        missing = [{"id": str(r["id"]), "title": r["title"]} for r in rows if not r["title_en"]]
        if missing:
            raise ApiError(
                422,
                "title_en_required",
                f"영문 제목이 없는 항목 {len(missing)}개에 영문 제목을 먼저 넣어야 한다.",
            )
    await check_daily_limit(db, ["generate_document"], settings.daily_limit_document)
    version = await db.scalar(
        """select coalesce(max(version), 0) + 1 from document_versions
           where document_id = :id and user_id = :user_id""",
        id=document_id,
    )
    row = await db.one(
        f"""insert into document_versions (document_id, user_id, version, selected_item_ids, options)
            values (:doc, :user_id, :version, :ids, cast(:options as jsonb))
            returning {VERSION_COLUMNS}""",
        doc=document_id,
        version=version,
        ids=ids,
        options=as_json(body.options),
    )
    await db.execute(
        "update documents set updated_at = now() where id = :id and user_id = :user_id",
        id=document_id,
    )
    job_id = await enqueue(db, "generate_document", {"version_id": str(row["id"])})
    return {"version": row, "job_id": job_id}


async def _version(db: UserDB, document_id: UUID, version: int) -> dict:
    row = await db.one(
        f"""select {VERSION_COLUMNS}, content, pdf_path from document_versions
            where document_id = :doc and version = :v and user_id = :user_id""",
        doc=document_id,
        v=version,
    )
    if row is None:
        raise not_found("문서 버전을 찾을 수 없다.")
    return row


@router.get("/documents/{document_id}/versions/{version}")
async def get_version(document_id: UUID, version: int, db: UserDB = Depends(get_user_db)):
    doc = await _doc(db, document_id)
    row = await _version(db, document_id, version)
    row.pop("pdf_path")
    row["html"] = (
        render_html(doc["format"], row["content"], title=doc["title"], for_pdf=False)
        if row["content"]
        else None
    )
    return row


@router.get("/documents/{document_id}/versions/{version}/html", response_class=HTMLResponse)
async def version_html(document_id: UUID, version: int, db: UserDB = Depends(get_user_db)):
    doc = await _doc(db, document_id)
    row = await _version(db, document_id, version)
    if not row["content"]:
        raise not_found("아직 만들어지지 않은 버전이다.")
    return render_html(doc["format"], row["content"], title=doc["title"], for_pdf=False)


@router.get("/documents/{document_id}/versions/{version}/pdf")
async def version_pdf(
    document_id: UUID,
    version: int,
    db: UserDB = Depends(get_user_db),
    settings: Settings = Depends(get_settings),
):
    doc = await _doc(db, document_id)
    row = await _version(db, document_id, version)
    if not row["pdf_path"]:
        raise not_found("PDF가 없는 버전이다.")
    ttl = settings.signed_url_ttl_seconds
    url = await get_storage().signed_url(
        "documents", row["pdf_path"], ttl, download_name=f"{doc['title']}_v{version}.pdf"
    )
    return {"url": url, "expires_in": ttl}
