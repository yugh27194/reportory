"""초기 데이터 가져오기 작업(인계서 13.1절 import_resume, import_github, import_linkedin)."""

from uuid import UUID

from app.db import UserDB, as_json
from app.importers.common import reset_import
from app.importers.github import GitHubError, run_github
from app.importers.linkedin import run_linkedin
from app.importers.resume import run_resume
from app.storage import get_storage
from app.uploads import sniff

SOURCE_LABELS = {"resume_file": "이력서", "github": "GitHub", "linkedin_zip": "LinkedIn"}


async def _start(db: UserDB, import_id: UUID) -> dict | None:
    row = await db.one(
        "select id, source, storage_path from imports where id = :id and user_id = :user_id",
        id=import_id,
    )
    if row is None:
        return None
    await reset_import(db, import_id)
    await db.execute(
        "update imports set status = 'running' where id = :id and user_id = :user_id",
        id=import_id,
    )
    return row


async def _finish(db: UserDB, row: dict, summary: dict) -> dict:
    await db.execute(
        """update imports set status = 'succeeded', summary = cast(:s as jsonb),
             finished_at = now(), error = null
           where id = :id and user_id = :user_id""",
        id=row["id"],
        s=as_json(summary),
    )
    n = summary.get("items_proposed", 0)
    await db.execute(
        """insert into notifications (user_id, type, title, link, ref_id)
           values (:user_id, 'proposals_ready', :title, '/review', :id)
           on conflict do nothing""",
        id=row["id"],
        title=f"{SOURCE_LABELS.get(row['source'], '가져오기')}에서 항목 제안 {n}건을 만들었다.",
    )
    return summary


async def run_resume_job(db: UserDB, payload: dict) -> dict:
    row = await _start(db, UUID(payload["import_id"]))
    if row is None:
        return {"skipped": "import_deleted"}
    data = await get_storage().get("imports", row["storage_path"])
    result = await run_resume(db, row["id"], data, sniff(data) or "application/pdf")
    return await _finish(db, row, result.as_dict())


async def run_linkedin_job(db: UserDB, payload: dict) -> dict:
    row = await _start(db, UUID(payload["import_id"]))
    if row is None:
        return {"skipped": "import_deleted"}
    data = await get_storage().get("imports", row["storage_path"])
    result = await run_linkedin(db, row["id"], data)
    return await _finish(db, row, result.as_dict())


async def _scrub_token(db: UserDB, import_id: str) -> None:
    """GitHub 토큰은 작업이 끝나면 작업 큐에서 지운다."""
    await db.execute(
        """update jobs set payload = payload - 'provider_token'
           where user_id = :user_id and type = 'import_github'
             and payload ->> 'import_id' = :iid""",
        iid=import_id,
    )


async def run_github_job(db: UserDB, payload: dict) -> dict:
    row = await _start(db, UUID(payload["import_id"]))
    if row is None:
        return {"skipped": "import_deleted"}
    token = payload.get("provider_token")
    if not token:
        raise GitHubError("GitHub 토큰이 없다. GitHub로 다시 로그인한 뒤 시도해야 한다.")
    result = await run_github(db, row["id"], token)
    await _scrub_token(db, payload["import_id"])
    return await _finish(db, row, result.as_dict())


async def on_final_failure(db: UserDB, payload: dict) -> None:
    await db.execute(
        """update imports set status = 'failed', finished_at = now(),
             error = '가져오기에 실패했다. 파일이나 권한을 확인한 뒤 다시 시도해 보세요.'
           where id = :id and user_id = :user_id""",
        id=UUID(payload["import_id"]),
    )
    await _scrub_token(db, payload["import_id"])
