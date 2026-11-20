"""항목 조회·생성·패치·병합(인계서 8.2절, 11.2절)."""

from datetime import date
from typing import Any
from uuid import UUID

from app.db import UserDB, as_json
from app.errors import not_found, validation_error
from app.llm.schemas import DETAILS_KEYS
from app.services.jobs import enqueue
from app.services.skills import link_skills, skills_of

ITEM_COLUMNS = """id, type, status, title, title_en, organization, role, start_date, end_date,
  is_ongoing, summary, details, metrics, links, visibility, created_at, updated_at, approved_at"""


async def get_item(db: UserDB, item_id: UUID, *, statuses: tuple[str, ...] | None = None) -> dict:
    row = await db.one(
        f"select {ITEM_COLUMNS} from items where id = :id and user_id = :user_id", id=item_id
    )
    if row is None or (statuses is not None and row["status"] not in statuses):
        raise not_found("항목을 찾을 수 없다.")
    return row


async def item_detail(db: UserDB, item_id: UUID) -> dict:
    item = await get_item(db, item_id)
    item["skills"] = await skills_of(db, item_id)
    item["sources"] = await db.all(
        """select s.id, s.entry_id, s.import_id, s.evidence_id, s.followup_id, s.quote,
                  s.created_at, e.entry_date
           from item_sources s left join entries e on e.id = s.entry_id
           where s.item_id = :item_id and s.user_id = :user_id order by s.created_at""",
        item_id=item_id,
    )
    item["applications"] = await db.all(
        """select id, title, status from applications
           where item_id = :item_id and user_id = :user_id order by created_at""",
        item_id=item_id,
    )
    return item


def filter_details(item_type: str, details: dict[str, Any]) -> dict[str, Any]:
    allowed = DETAILS_KEYS.get(item_type, ())
    return {k: v for k, v in details.items() if k in allowed and v is not None}


def merge_metrics(current: list[dict], new: list[dict]) -> list[dict]:
    """이름이 같은 수치는 교체하고, 새 이름은 덧붙인다."""
    by_name = {m["name"]: m for m in current}
    order = [m["name"] for m in current]
    for m in new:
        if m["name"] not in by_name:
            order.append(m["name"])
        by_name[m["name"]] = m
    return [by_name[n] for n in order]


def append_summary(current: str, addition: str) -> str:
    addition = (addition or "").strip()
    if not addition:
        return current
    return f"{current.strip()} {addition}".strip()


async def apply_patch(db: UserDB, item_id: UUID, patch: dict[str, Any]) -> None:
    """update_item 제안의 patch를 적용한다(8.2절 규칙)."""
    item = await get_item(db, item_id, statuses=("approved", "proposed"))
    summary = append_summary(item["summary"], patch.get("summary_append", ""))
    metrics = merge_metrics(item["metrics"], patch.get("metrics_add") or [])
    details = {**item["details"], **filter_details(item["type"], patch.get("details_patch") or {})}
    end_date = patch.get("end_date") or item["end_date"]
    is_ongoing = item["is_ongoing"] if patch.get("is_ongoing") is None else patch["is_ongoing"]
    role = patch.get("role") or item["role"]
    if isinstance(end_date, str):
        end_date = date.fromisoformat(end_date)
    await db.execute(
        """update items set summary = :summary, metrics = cast(:metrics as jsonb),
             details = cast(:details as jsonb), end_date = :end_date, is_ongoing = :is_ongoing,
             role = :role
           where id = :id and user_id = :user_id""",
        id=item_id,
        summary=summary,
        metrics=as_json(metrics),
        details=as_json(details),
        end_date=end_date,
        is_ongoing=is_ongoing,
        role=role,
    )
    await link_skills(db, item_id, patch.get("skills_add") or [])
    if item["status"] == "approved":
        await enqueue(db, "embed_item", {"item_id": str(item_id)})


async def add_source(
    db: UserDB,
    item_id: UUID,
    *,
    entry_id: UUID | None = None,
    import_id: UUID | None = None,
    evidence_id: UUID | None = None,
    followup_id: UUID | None = None,
    quote: str | None = None,
) -> None:
    await db.execute(
        """insert into item_sources (item_id, user_id, entry_id, import_id, evidence_id,
                                     followup_id, quote)
           select i.id, i.user_id, v.entry_id, v.import_id, v.evidence_id, v.followup_id, v.quote
           from items i,
             (select cast(:entry_id as uuid) entry_id, cast(:import_id as uuid) import_id,
                     cast(:evidence_id as uuid) evidence_id, cast(:followup_id as uuid) followup_id,
                     cast(:quote as text) quote) v
           where i.id = :item_id and i.user_id = :user_id
             and not exists (
               select 1 from item_sources s where s.item_id = i.id
                 and s.entry_id is not distinct from v.entry_id
                 and s.followup_id is not distinct from v.followup_id
                 and s.import_id is not distinct from v.import_id
                 and s.evidence_id is not distinct from v.evidence_id
                 and s.quote is not distinct from v.quote)""",
        item_id=item_id,
        entry_id=entry_id,
        import_id=import_id,
        evidence_id=evidence_id,
        followup_id=followup_id,
        quote=quote,
    )


async def merge_items(db: UserDB, keep_id: UUID, merge_ids: list[UUID]) -> None:
    """근거·기술·증빙·지원·질문 연결을 남길 항목으로 옮기고, 나머지는 archived로 바꾼다."""
    merge_ids = [m for m in dict.fromkeys(merge_ids) if m != keep_id]
    if not merge_ids:
        raise validation_error("합칠 항목을 하나 이상 골라야 한다.")
    await get_item(db, keep_id, statuses=("approved", "proposed"))
    count = await db.scalar(
        """select count(*) from items where user_id = :user_id and id = any(:ids)
             and status in ('approved', 'proposed')""",
        ids=merge_ids,
    )
    if count != len(merge_ids):
        raise not_found("합칠 항목을 찾을 수 없다.")
    params = {"keep": keep_id, "ids": merge_ids}
    await db.execute(
        """update item_sources set item_id = :keep
           where user_id = :user_id and item_id = any(:ids)""",
        **params,
    )
    await db.execute(
        """insert into item_skills (item_id, skill_id, user_id)
           select cast(:keep as uuid), skill_id, user_id from item_skills
           where user_id = :user_id and item_id = any(:ids) on conflict do nothing""",
        **params,
    )
    await db.execute(
        "delete from item_skills where user_id = :user_id and item_id = any(:ids)", **params
    )
    for table in ("evidence", "applications", "followup_questions"):
        await db.execute(
            f"update {table} set item_id = :keep where user_id = :user_id and item_id = any(:ids)",
            **params,
        )
    await db.execute(
        """update proposals set status = 'rejected', resolved_at = now()
           where user_id = :user_id and status = 'pending' and item_id = any(:ids)""",
        **params,
    )
    await db.execute(
        """update items set status = 'archived'
           where user_id = :user_id and id = any(:ids)""",
        **params,
    )
    keep = await get_item(db, keep_id)
    if keep["status"] == "approved":
        await enqueue(db, "embed_item", {"item_id": str(keep_id)})
