"""검토 큐 제안 승인·거절(인계서 8.2절)."""

from datetime import date
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, ValidationError, field_validator

from app.db import UserDB, as_json
from app.errors import ApiError, invalid_transition, not_found, validation_error
from app.llm.schemas import Metric
from app.llm.validators import date_in_range
from app.services.items import add_source, apply_patch, filter_details, get_item, merge_items
from app.services.jobs import enqueue
from app.services.skills import link_skills

BULK_MIN_CONFIDENCE = 0.8


class ItemEdit(BaseModel):
    """create_item 제안을 '수정 후 승인'할 때 받는 값."""

    title: str | None = Field(default=None, min_length=1, max_length=200)
    organization: str | None = None
    role: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    is_ongoing: bool | None = None
    summary: str | None = None
    metrics: list[Metric] | None = None
    details: dict[str, Any] | None = None
    skills: list[str] | None = None


class PatchEdit(BaseModel):
    """update_item 제안의 patch를 수정할 때 받는 값."""

    summary_append: str = ""
    end_date: date | None = None
    is_ongoing: bool | None = None
    role: str | None = None
    metrics_add: list[Metric] = []
    skills_add: list[str] = []
    details_patch: dict[str, Any] = {}

    @field_validator("summary_append")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()


def _check_dates(values: dict[str, Any]) -> None:
    today = date.today()
    for key in ("start_date", "end_date"):
        v = values.get(key)
        if v is not None and not date_in_range(v, today):
            raise validation_error("날짜가 허용 범위(오늘 기준 ±10년)를 벗어났다.")
    start, end = values.get("start_date"), values.get("end_date")
    if start and end and end < start:
        raise validation_error("종료일이 시작일보다 앞선다.")
    if end and end > today and values.get("is_ongoing") is False:
        raise validation_error("진행 중이 아닌 항목의 종료일은 미래일 수 없다.")


async def _load_pending(db: UserDB, proposal_id: UUID) -> dict:
    row = await db.one(
        """select id, kind, status, payload, item_id, entry_id, import_id, evidence_id,
                  confidence, quote
           from proposals where id = :id and user_id = :user_id for update""",
        id=proposal_id,
    )
    if row is None:
        raise not_found("제안을 찾을 수 없다.")
    if row["status"] != "pending":
        raise invalid_transition("이미 처리한 제안이다.")
    return row


async def _resolve(db: UserDB, proposal_id: UUID, status: str, payload: dict | None = None) -> None:
    if payload is None:
        await db.execute(
            """update proposals set status = cast(:status as proposal_status), resolved_at = now()
               where id = :id and user_id = :user_id""",
            id=proposal_id,
            status=status,
        )
    else:
        await db.execute(
            """update proposals set status = cast(:status as proposal_status), resolved_at = now(),
                 payload = cast(:payload as jsonb)
               where id = :id and user_id = :user_id""",
            id=proposal_id,
            status=status,
            payload=as_json(payload),
        )


async def _accept_create_item(db: UserDB, p: dict, edited: dict | None) -> None:
    item_id = UUID(p["payload"]["item_id"])
    item = await get_item(db, item_id)
    if item["status"] != "proposed":
        raise invalid_transition("이 항목은 이미 처리됐다.")
    if edited:
        try:
            edit = ItemEdit.model_validate(edited)
        except ValidationError as exc:
            raise validation_error("수정한 값이 올바르지 않다.") from exc
        values = edit.model_dump(exclude_unset=True)
        merged = {**item, **values}
        _check_dates(merged)
        await db.execute(
            """update items set title = :title, organization = :organization, role = :role,
                 start_date = :start_date, end_date = :end_date, is_ongoing = :is_ongoing,
                 summary = :summary, metrics = cast(:metrics as jsonb),
                 details = cast(:details as jsonb)
               where id = :id and user_id = :user_id""",
            id=item_id,
            title=merged["title"],
            organization=merged["organization"],
            role=merged["role"],
            start_date=merged["start_date"],
            end_date=merged["end_date"],
            is_ongoing=bool(merged["is_ongoing"]),
            summary=merged["summary"] or "",
            metrics=as_json(
                [m if isinstance(m, dict) else m.model_dump() for m in merged["metrics"]]
            ),
            details=as_json(filter_details(item["type"], merged["details"] or {})),
        )
        if edit.skills is not None:
            await db.execute(
                "delete from item_skills where item_id = :id and user_id = :user_id", id=item_id
            )
            await link_skills(db, item_id, edit.skills)
    await db.execute(
        """update items set status = 'approved', approved_at = now()
           where id = :id and user_id = :user_id""",
        id=item_id,
    )
    await enqueue(db, "embed_item", {"item_id": str(item_id)})


async def _accept_update_item(db: UserDB, p: dict, edited: dict | None) -> dict:
    payload = dict(p["payload"])
    item_id = UUID(payload["item_id"])
    if edited:
        try:
            patch = PatchEdit.model_validate(edited.get("patch", edited))
        except ValidationError as exc:
            raise validation_error("수정한 값이 올바르지 않다.") from exc
        _check_dates({"end_date": patch.end_date, "is_ongoing": patch.is_ongoing})
        payload["patch"] = patch.model_dump(mode="json")
    await apply_patch(db, item_id, payload["patch"])
    followup_id = payload.get("followup_id")
    if p["entry_id"] or followup_id:
        await add_source(
            db,
            item_id,
            entry_id=p["entry_id"],
            followup_id=UUID(followup_id) if followup_id else None,
            quote=p["quote"],
        )
    return payload


async def _accept_link_entry(db: UserDB, p: dict) -> None:
    payload = p["payload"]
    item_id = UUID(payload["item_id"])
    await get_item(db, item_id, statuses=("approved", "proposed"))
    await add_source(db, item_id, entry_id=UUID(payload["entry_id"]), quote=payload.get("quote"))


async def accept(db: UserDB, proposal_id: UUID, edited: dict | None = None) -> dict:
    p = await _load_pending(db, proposal_id)
    payload = None
    match p["kind"]:
        case "create_item":
            await _accept_create_item(db, p, edited)
        case "update_item":
            payload = await _accept_update_item(db, p, edited)
        case "link_entry":
            await _accept_link_entry(db, p)
        case "merge_items":
            data = edited or p["payload"]
            await merge_items(
                db, UUID(str(data["keep_item_id"])), [UUID(str(i)) for i in data["merge_item_ids"]]
            )
            payload = data if edited else None
        case _:
            raise ApiError(422, "validation_error", "이 제안 종류는 아직 처리할 수 없다.")
    await _resolve(db, proposal_id, "accepted", payload if edited else None)
    return {"id": proposal_id, "status": "accepted"}


async def reject(db: UserDB, proposal_id: UUID) -> dict:
    p = await _load_pending(db, proposal_id)
    await _resolve(db, proposal_id, "rejected")
    if p["kind"] == "create_item":
        item_id = UUID(p["payload"]["item_id"])
        await reject_proposed_item(db, item_id)
    return {"id": proposal_id, "status": "rejected"}


async def reject_proposed_item(db: UserDB, item_id: UUID) -> None:
    """제안 상태 항목을 거절하고, 그 항목을 가리키는 대기 제안도 함께 거절한다."""
    await db.execute(
        """update items set status = 'rejected'
           where id = :id and user_id = :user_id and status = 'proposed'""",
        id=item_id,
    )
    await db.execute(
        """update proposals set status = 'rejected', resolved_at = now()
           where user_id = :user_id and status = 'pending'
             and (item_id = :id or payload ->> 'item_id' = cast(:id as text))""",
        id=item_id,
    )


async def bulk_accept(db: UserDB, ids: list[UUID]) -> list[dict]:
    ids = list(dict.fromkeys(ids))
    rows = await db.all(
        """select id, kind, confidence, status from proposals
           where user_id = :user_id and id = any(:ids)""",
        ids=ids,
    )
    if len(rows) != len(ids):
        raise not_found("제안을 찾을 수 없다.")
    if any(r["status"] != "pending" for r in rows):
        raise invalid_transition("이미 처리한 제안이 섞여 있다.")
    if any(r["confidence"] is None or r["confidence"] < BULK_MIN_CONFIDENCE for r in rows):
        raise validation_error("신뢰도 0.8 미만인 제안은 일괄 승인할 수 없다.")
    # create_item을 먼저 승인해야 같은 항목의 update·link가 승인된 항목에 붙는다.
    kinds = {r["id"]: r["kind"] for r in rows}
    ordered = sorted(ids, key=lambda i: 0 if kinds[i] == "create_item" else 1)
    return [await accept(db, i) for i in ordered]


async def reject_pending_for_entry(db: UserDB, entry_id: UUID) -> int:
    """일기 재추출·삭제 전에 그 일기에서 나온 대기 제안을 거절한다. 승인된 데이터는 건드리지 않는다."""
    created = await db.all(
        """select payload ->> 'item_id' as item_id from proposals
           where user_id = :user_id and entry_id = :entry_id and status = 'pending'
             and kind = 'create_item'""",
        entry_id=entry_id,
    )
    for row in created:
        await reject_proposed_item(db, UUID(row["item_id"]))
    n = await db.execute(
        """update proposals set status = 'rejected', resolved_at = now()
           where user_id = :user_id and entry_id = :entry_id and status = 'pending'""",
        entry_id=entry_id,
    )
    await db.execute(
        """update followup_questions set status = 'dismissed'
           where user_id = :user_id and entry_id = :entry_id and status = 'open'""",
        entry_id=entry_id,
    )
    return n + len(created)
