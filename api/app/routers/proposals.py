"""검토 큐(인계서 9.2절 /proposals, 11.1절)."""

from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.db import UserDB, get_user_db
from app.services import proposals as svc

router = APIRouter(tags=["proposals"])


@router.get("/proposals")
async def list_proposals(
    status: Literal["pending", "accepted", "rejected"] = "pending",
    db: UserDB = Depends(get_user_db),
):
    rows = await db.all(
        """select p.id, p.kind, p.status, p.payload, p.item_id, p.entry_id, p.confidence,
                  p.quote, p.possible_duplicate_of, p.created_at,
                  e.entry_date, e.body as entry_body,
                  to_jsonb(i) - 'embedding' - 'user_id' as item,
                  (select coalesce(jsonb_agg(s.name order by s.name), '[]'::jsonb)
                     from item_skills isk join skills s on s.id = isk.skill_id
                    where isk.item_id = p.item_id and isk.user_id = p.user_id) as item_skills,
                  (select to_jsonb(d) - 'embedding' - 'user_id' from items d
                    where d.id = p.possible_duplicate_of and d.user_id = p.user_id) as duplicate
           from proposals p
           left join entries e on e.id = p.entry_id and e.user_id = p.user_id
           left join items i on i.id = p.item_id and i.user_id = p.user_id
           where p.user_id = :user_id and p.status = cast(:status as proposal_status)
           order by p.created_at desc limit 200""",
        status=status,
    )
    return {"proposals": rows}


@router.get("/proposals/count")
async def pending_count(db: UserDB = Depends(get_user_db)):
    return {
        "proposals": await db.scalar(
            "select count(*) from proposals where user_id = :user_id and status = 'pending'"
        ),
        "followups": await db.scalar(
            "select count(*) from followup_questions where user_id = :user_id and status = 'open'"
        ),
    }


class AcceptIn(BaseModel):
    edited_payload: dict[str, Any] | None = None


@router.post("/proposals/{proposal_id}/accept")
async def accept(
    proposal_id: UUID, body: AcceptIn | None = None, db: UserDB = Depends(get_user_db)
):
    return await svc.accept(db, proposal_id, body.edited_payload if body else None)


@router.post("/proposals/{proposal_id}/reject")
async def reject(proposal_id: UUID, db: UserDB = Depends(get_user_db)):
    return await svc.reject(db, proposal_id)


class BulkIn(BaseModel):
    ids: list[UUID] = Field(min_length=1, max_length=100)


@router.post("/proposals/bulk-accept")
async def bulk_accept(body: BulkIn, db: UserDB = Depends(get_user_db)):
    return {"results": await svc.bulk_accept(db, body.ids)}
