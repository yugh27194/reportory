"""일기 추출 작업(인계서 10.2절)."""

from datetime import date
from typing import Any
from uuid import UUID

from app.db import UserDB, as_json
from app.llm.calls import call_logger
from app.llm.client import get_llm
from app.llm.schemas import ExtractionResult, ItemCandidate
from app.llm.validators import validate_extraction
from app.services.applications import OPEN_STATUSES, is_allowed
from app.services.proposals import reject_pending_for_entry
from app.services.similarity import find_duplicates, safe_embed
from app.services.skills import link_skills

KNOWN_ITEMS_LIMIT = 40
RECENT_ITEMS = 20
SIMILAR_ITEMS = 20


async def known_items(db: UserDB, entry_body: str) -> list[dict[str, Any]]:
    """KNOWN_ITEMS 문맥(10.2절).

    40개 이하이면 모두 넣는다. 넘으면 최근 수정 20개, 일기 임베딩과 유사도 상위 20개,
    진행 중 항목을 넣는다. 임베딩을 쓸 수 없으면 유사도 몫은 빠진다.
    """
    where = "user_id = :user_id and status in ('approved', 'proposed')"
    total = await db.scalar(f"select count(*) from items where {where}")
    if total > KNOWN_ITEMS_LIMIT:
        ids = {
            r["id"]
            for r in await db.all(
                f"""(select id from items where {where} order by updated_at desc
                     limit {RECENT_ITEMS})
                    union (select id from items where {where} and is_ongoing)"""
            )
        }
        vectors = await safe_embed([entry_body])
        if vectors:
            similar = await db.all(
                f"""select id from items where {where} and embedding is not null
                    order by embedding <=> cast(:v as vector) limit {SIMILAR_ITEMS}""",
                v=str(vectors[0]),
            )
            ids |= {r["id"] for r in similar}
        rows = await db.all(
            f"select * from items where {where} and id = any(:ids) order by updated_at desc",
            ids=list(ids),
        )
    else:
        rows = await db.all(f"select * from items where {where} order by updated_at desc")
    out = []
    for r in rows:
        skills = await db.all(
            """select s.name from item_skills isk join skills s on s.id = isk.skill_id
               where isk.item_id = :item_id and isk.user_id = :user_id
               order by s.name limit 5""",
            item_id=r["id"],
        )
        out.append(
            {
                "id": str(r["id"]),
                "type": r["type"],
                "title": r["title"],
                "organization": r["organization"],
                "start_date": r["start_date"],
                "end_date": r["end_date"],
                "is_ongoing": r["is_ongoing"],
                "skills": [s["name"] for s in skills],
            }
        )
    return out


async def open_applications(db: UserDB) -> list[dict[str, Any]]:
    rows = await db.all(
        """select id, title, organizer, status, result_announce_on, activity_start, activity_end
           from applications where user_id = :user_id and status = any(cast(:st as application_status[]))""",
        st=list(OPEN_STATUSES),
    )
    return [{**r, "id": str(r["id"])} for r in rows]


async def _create_item(db: UserDB, cand: ItemCandidate, entry_id: UUID, dup: UUID | None) -> UUID:
    item_id = await db.scalar(
        """insert into items (user_id, type, status, title, organization, role, start_date,
             end_date, is_ongoing, summary, details, metrics)
           values (:user_id, cast(:type as item_type), 'proposed', :title, :organization, :role,
             :start_date, :end_date, :is_ongoing, :summary, cast(:details as jsonb),
             cast(:metrics as jsonb))
           returning id""",
        type=cand.type,
        title=cand.title[:200],
        organization=cand.organization,
        role=cand.role,
        start_date=cand.start_date,
        end_date=cand.end_date,
        is_ongoing=bool(cand.is_ongoing),
        summary=cand.summary_append,
        details=as_json(cand.details),
        metrics=as_json([m.model_dump() for m in cand.metrics]),
    )
    await link_skills(db, item_id, cand.skills)
    await db.execute(
        """insert into item_sources (item_id, user_id, entry_id, quote)
           values (:item_id, :user_id, :entry_id, :quote)""",
        item_id=item_id,
        entry_id=entry_id,
        quote=cand.quote,
    )
    await _proposal(
        db,
        "create_item",
        {"item_id": str(item_id)},
        item_id=item_id,
        entry_id=entry_id,
        cand=cand,
        possible_duplicate_of=dup,
    )
    return item_id


async def _proposal(
    db: UserDB,
    kind: str,
    payload: dict,
    *,
    entry_id: UUID,
    item_id: UUID | None = None,
    application_id: UUID | None = None,
    cand: Any = None,
    possible_duplicate_of: UUID | None = None,
) -> None:
    await db.execute(
        """insert into proposals (user_id, kind, payload, item_id, application_id, entry_id,
             confidence, quote, possible_duplicate_of)
           values (:user_id, cast(:kind as proposal_kind), cast(:payload as jsonb), :item_id,
             :application_id, :entry_id, :confidence, :quote, :dup)""",
        kind=kind,
        payload=as_json(payload),
        item_id=item_id,
        application_id=application_id,
        entry_id=entry_id,
        confidence=cand.confidence if cand else None,
        quote=cand.quote if cand else None,
        dup=possible_duplicate_of,
    )


def update_patch(cand: ItemCandidate) -> dict[str, Any]:
    return {
        "summary_append": cand.summary_append,
        "end_date": cand.end_date.isoformat() if cand.end_date else None,
        "is_ongoing": cand.is_ongoing,
        "role": cand.role,
        "metrics_add": [m.model_dump() for m in cand.metrics],
        "skills_add": cand.skills,
        "details_patch": cand.details,
    }


async def run(db: UserDB, payload: dict) -> dict:
    entry_id = UUID(payload["entry_id"])
    entry = await db.one(
        "select id, entry_date, body from entries where id = :id and user_id = :user_id",
        id=entry_id,
    )
    if entry is None:
        return {"skipped": "entry_deleted"}

    # 멱등: 같은 일기의 대기 제안을 먼저 정리한다(13.1절).
    await reject_pending_for_entry(db, entry_id)
    await db.execute(
        "update entries set extraction_status = 'running' where id = :id and user_id = :user_id",
        id=entry_id,
    )

    items_ctx = await known_items(db, entry["body"])
    apps_ctx = await open_applications(db)
    entry_date: date = entry["entry_date"]

    raw = await get_llm().complete_json(
        "extract_entry",
        "extract_entry",
        {
            "ENTRY_DATE": entry_date.isoformat(),
            "ENTRY": entry["body"],
            "KNOWN_ITEMS": items_ctx,
            "OPEN_APPLICATIONS": apps_ctx,
        },
        ExtractionResult,
        "extract",
        user_id=db.user_id,
        log_call=call_logger(db),
    )
    result, report, _ = validate_extraction(
        raw,
        entry["body"],
        entry_date,
        known_item_ids={UUID(i["id"]) for i in items_ctx},
        open_application_ids={UUID(a["id"]) for a in apps_ctx},
    )

    creates = [i for i, c in enumerate(result.items) if c.action == "create"]
    dups = dict(
        zip(creates, await find_duplicates(db, [result.items[i] for i in creates]), strict=True)
    )
    created: dict[int, UUID] = {}
    proposals = 0
    for idx, cand in enumerate(result.items):
        if cand.action == "create":
            created[idx] = await _create_item(db, cand, entry_id, dups[idx])
        elif cand.action == "update":
            await _proposal(
                db,
                "update_item",
                {"item_id": str(cand.target_item_id), "patch": update_patch(cand)},
                item_id=cand.target_item_id,
                entry_id=entry_id,
                cand=cand,
            )
        else:
            await _proposal(
                db,
                "link_entry",
                {
                    "item_id": str(cand.target_item_id),
                    "entry_id": str(entry_id),
                    "quote": cand.quote,
                },
                item_id=cand.target_item_id,
                entry_id=entry_id,
                cand=cand,
            )
        proposals += 1

    app_status = {UUID(a["id"]): a["status"] for a in apps_ctx}
    for upd in result.application_updates:
        if not is_allowed(app_status[upd.application_id], upd.to_status):
            report.dropped_application_updates += 1
            continue
        await _proposal(
            db,
            "application_update",
            {
                "application_id": str(upd.application_id),
                "to_status": upd.to_status,
                "result_date": upd.result_date.isoformat() if upd.result_date else None,
                "quote": upd.quote,
            },
            application_id=upd.application_id,
            entry_id=entry_id,
            cand=upd,
        )
        proposals += 1

    followups = 0
    for f in result.followups:
        kind, _, ref = f.target.partition(":")
        item_id = created.get(int(ref)) if kind == "candidate" else UUID(ref)
        if item_id is None:  # update·link 후보를 가리키는 질문은 그 대상 항목에 붙인다
            cand = result.items[int(ref)]
            item_id = cand.target_item_id
        if item_id is None:
            continue
        await db.execute(
            """insert into followup_questions (user_id, item_id, entry_id, question, reason)
               values (:user_id, :item_id, :entry_id, :question, :reason)""",
            item_id=item_id,
            entry_id=entry_id,
            question=f.question,
            reason=f.reason,
        )
        followups += 1

    await db.execute(
        """update entries set extraction_status = 'succeeded', extracted_at = now()
           where id = :id and user_id = :user_id""",
        id=entry_id,
    )
    if proposals or followups:
        await db.execute(
            """insert into notifications (user_id, type, title, link)
               values (:user_id, 'proposals_ready', :title, '/review')""",
            title=f"일기에서 제안 {proposals}건, 질문 {followups}건을 찾았다.",
        )
    return {
        "is_relevant": result.is_relevant,
        "proposals": proposals,
        "followups": followups,
        "dropped_candidates": report.dropped_candidates,
        "dropped_values": report.dropped_values,
    }


async def on_final_failure(db: UserDB, payload: dict) -> None:
    await db.execute(
        "update entries set extraction_status = 'failed' where id = :id and user_id = :user_id",
        id=UUID(payload["entry_id"]),
    )
