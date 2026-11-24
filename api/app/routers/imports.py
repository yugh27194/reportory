"""초기 데이터 가져오기(인계서 9.2절 /imports, 11.6절)."""

import uuid
from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile
from pydantic import BaseModel, Field

from app.config import Settings, get_settings
from app.db import UserDB, get_user_db
from app.errors import ApiError, not_found
from app.routers.me import ensure_profile
from app.services.jobs import check_daily_limit, enqueue
from app.storage import get_storage
from app.uploads import MIME_EXT, check_upload, check_zip_safety

router = APIRouter(tags=["imports"])

IMPORT_JOBS = ["import_resume", "import_github", "import_linkedin"]
RESUME_MIME = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
IMPORT_COLUMNS = "id, source, status, summary, error, created_at, finished_at"


async def _prepare(db: UserDB, settings: Settings, needs_llm: bool) -> None:
    profile = await ensure_profile(db)
    if needs_llm and profile["llm_consent_at"] is None:
        raise ApiError(
            403, "consent_required", "파일 분석을 쓰려면 먼저 외부 LLM 처리에 동의해야 한다."
        )
    await check_daily_limit(db, IMPORT_JOBS, settings.daily_limit_import)


async def _create(db: UserDB, source: str, path: str | None) -> dict:
    return await db.one(
        f"""insert into imports (user_id, source, storage_path)
            values (:user_id, cast(:source as import_source), :path)
            returning {IMPORT_COLUMNS}""",
        source=source,
        path=path,
    )


async def _store(db: UserDB, data: bytes, mime: str) -> str:
    path = f"{db.user_id}/{uuid.uuid4()}.{MIME_EXT[mime]}"
    await get_storage().put("imports", path, data, mime)
    return path


@router.post("/imports/resume", status_code=202)
async def import_resume(
    file: UploadFile = File(...),
    db: UserDB = Depends(get_user_db),
    settings: Settings = Depends(get_settings),
):
    data = await file.read()
    mime = check_upload(data, RESUME_MIME)
    await _prepare(db, settings, needs_llm=True)
    row = await _create(db, "resume_file", await _store(db, data, mime))
    job_id = await enqueue(db, "import_resume", {"import_id": str(row["id"])})
    return {"import": row, "job_id": job_id}


@router.post("/imports/linkedin", status_code=202)
async def import_linkedin(
    file: UploadFile = File(...),
    db: UserDB = Depends(get_user_db),
    settings: Settings = Depends(get_settings),
):
    data = await file.read()
    check_upload(data, {"application/zip"}, max_mb=50)
    check_zip_safety(data)
    await _prepare(db, settings, needs_llm=False)
    row = await _create(db, "linkedin_zip", await _store(db, data, "application/zip"))
    job_id = await enqueue(db, "import_linkedin", {"import_id": str(row["id"])})
    return {"import": row, "job_id": job_id}


class GitHubIn(BaseModel):
    provider_token: str = Field(min_length=10, max_length=500)


@router.post("/imports/github", status_code=202)
async def import_github(
    body: GitHubIn, db: UserDB = Depends(get_user_db), settings: Settings = Depends(get_settings)
):
    await _prepare(db, settings, needs_llm=True)
    row = await _create(db, "github", None)
    job_id = await enqueue(
        db, "import_github", {"import_id": str(row["id"]), "provider_token": body.provider_token}
    )
    return {"import": row, "job_id": job_id}


@router.get("/imports")
async def list_imports(db: UserDB = Depends(get_user_db)):
    return {
        "imports": await db.all(
            f"""select {IMPORT_COLUMNS} from imports where user_id = :user_id and source <> 'manual'
            order by created_at desc limit 50"""
        )
    }


@router.get("/imports/{import_id}")
async def get_import(import_id: UUID, db: UserDB = Depends(get_user_db)):
    row = await db.one(
        f"select {IMPORT_COLUMNS} from imports where id = :id and user_id = :user_id",
        id=import_id,
    )
    if row is None:
        raise not_found("가져오기 기록을 찾을 수 없다.")
    return row
