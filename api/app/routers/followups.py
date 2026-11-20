"""후속 질문(인계서 9.2절 /followups, 10.3절)."""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.db import UserDB, get_user_db
from app.errors import invalid_transition, not_found
from app.services.jobs import enqueue

router = APIRouter(tags=["followups"])


@router.get("/followups")
async def list_followups(
    status: Literal["open", "answered", "dismissed"] = "open", db: UserDB = Depends(get_user_db)
):
    rows = await db.all(
        """select f.id, f.item_id, f.entry_id, f.question, f.reason, f.answer, f.status,
                  f.created_at, i.title as item_title, i.type as item_type
           from followup_questions f join items i on i.id = f.item_id
           where f.user_id = :user_id and f.status = cast(:status as followup_status)
             and i.status in ('approved', 'proposed')
           order by f.created_at desc limit 200""",
        status=status,
    )
    return {"followups": rows}


async def _open(db: UserDB, followup_id: UUID) -> dict:
    row = await db.one(
        "select id, status from followup_questions where id = :id and user_id = :user_id",
        id=followup_id,
    )
    if row is None:
        raise not_found("질문을 찾을 수 없다.")
    if row["status"] != "open":
        raise invalid_transition("이미 답했거나 닫은 질문이다.")
    return row


class AnswerIn(BaseModel):
    answer: str = Field(min_length=1, max_length=2000)


@router.post("/followups/{followup_id}/answer", status_code=202)
async def answer(followup_id: UUID, body: AnswerIn, db: UserDB = Depends(get_user_db)):
    await _open(db, followup_id)
    await db.execute(
        """update followup_questions set answer = :answer, status = 'answered',
             answered_at = now() where id = :id and user_id = :user_id""",
        id=followup_id,
        answer=body.answer,
    )
    return {"job_id": await enqueue(db, "answer_followup", {"followup_id": str(followup_id)})}


@router.post("/followups/{followup_id}/dismiss")
async def dismiss(followup_id: UUID, db: UserDB = Depends(get_user_db)):
    await _open(db, followup_id)
    await db.execute(
        """update followup_questions set status = 'dismissed'
           where id = :id and user_id = :user_id""",
        id=followup_id,
    )
    return {"id": followup_id, "status": "dismissed"}
