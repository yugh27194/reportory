"""작업 상태(인계서 9.2절 /jobs/{id})."""

from uuid import UUID

from fastapi import APIRouter, Depends

from app.db import UserDB, get_user_db
from app.errors import not_found

router = APIRouter(tags=["jobs"])


@router.get("/jobs/{job_id}")
async def get_job(job_id: UUID, db: UserDB = Depends(get_user_db)):
    row = await db.one(
        """select id, type, status, result, last_error, attempts, created_at, updated_at
           from jobs where id = :id and user_id = :user_id""",
        id=job_id,
    )
    if row is None:
        raise not_found("작업을 찾을 수 없다.")
    return row
