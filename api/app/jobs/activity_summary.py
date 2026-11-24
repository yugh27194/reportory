"""활동 요약 제안(activity_summary, 인계서 10.4절).

지원이 completed가 되거나 사용자가 '요약 다시 쓰기'를 누르면 돈다. 항목에 연결된 근거 인용을 날짜순으로
모아 요약을 만들고, 그 결과를 update_item 제안(요약 바꾸기)으로 넣는다. 바로 저장하지 않는다.
요약·역할·수치·기술은 근거 글에 있는 것만 남긴다.
"""

from uuid import UUID

from app.db import UserDB, as_json
from app.llm.calls import call_logger
from app.llm.client import get_llm
from app.llm.schemas import ActivitySummary
from app.llm.validators import drop_unsupported_sentences, normalize_ws, numbers_supported
from app.services.skills import normalize_skill


async def run(db: UserDB, payload: dict) -> dict:
    item_id = UUID(payload["item_id"])
    item = await db.one(
        """select id, type, title, organization, role, summary, start_date, end_date, status
           from items where id = :id and user_id = :user_id""",
        id=item_id,
    )
    if item is None or item["status"] != "approved":
        return {"skipped": "not_approved"}
    quotes = await db.all(
        """select coalesce(e.entry_date, s.created_at::date) as date, s.quote
           from item_sources s left join entries e on e.id = s.entry_id
           where s.user_id = :user_id and s.item_id = :id and s.quote is not null
             and char_length(s.quote) > 0
           order by 1, s.created_at""",
        id=item_id,
    )
    if not quotes:
        return {"skipped": "no_sources"}
    period = " ~ ".join(str(d) for d in (item["start_date"], item["end_date"]) if d)
    out = await get_llm().complete_json(
        "activity_summary",
        "activity_summary",
        {
            "ITEM": {
                "title": item["title"],
                "type": item["type"],
                "organization": item["organization"],
                "period": period,
                "summary": item["summary"],
            },
            "QUOTES": [{"date": str(q["date"]), "quote": q["quote"]} for q in quotes],
        },
        ActivitySummary,
        "extract",
        log_call=call_logger(db),
    )
    source = "\n".join(
        [item["title"], item["organization"] or "", item["summary"] or ""]
        + [q["quote"] for q in quotes]
    )
    summary, dropped = drop_unsupported_sentences(out.summary.strip(), source)
    if not summary:
        return {"skipped": "nothing_supported", "dropped": dropped}
    src_norm = normalize_ws(source).lower()
    role = out.role if out.role and normalize_ws(out.role).lower() in src_norm else None
    metrics = [
        m.model_dump()
        for m in out.metrics
        if numbers_supported(m.value, source) and normalize_ws(m.value) in normalize_ws(source)
    ]
    src_skill = normalize_skill(source)
    skills = [s for s in out.skills if normalize_skill(s) and normalize_skill(s) in src_skill]

    # 같은 항목의 이전 요약 제안이 남아 있으면 정리한다(두 번 돌아도 제안은 하나).
    await db.execute(
        """update proposals set status = 'rejected', resolved_at = now()
           where user_id = :user_id and item_id = :id and status = 'pending'
             and kind = 'update_item' and payload ->> 'source' = 'activity_summary'""",
        id=item_id,
    )
    patch = {"summary_replace": summary, "metrics_add": metrics, "skills_add": skills}
    if role and role != item["role"]:
        patch["role"] = role
    proposal_id = await db.scalar(
        """insert into proposals (user_id, kind, payload, item_id)
           values (:user_id, 'update_item', cast(:payload as jsonb), :id) returning id""",
        payload=as_json({"item_id": str(item_id), "patch": patch, "source": "activity_summary"}),
        id=item_id,
    )
    await db.execute(
        """insert into notifications (user_id, type, title, link, ref_id)
           values (:user_id, 'activity_summary', :title, :link, :pid)
           on conflict do nothing""",
        title=f"'{item['title'][:40]}' 활동 요약을 새로 만들었다. 확인하고 반영해 보세요.",
        link=f"/portfolio/{item_id}",
        pid=proposal_id,
    )
    return {"proposal_id": str(proposal_id), "dropped_sentences": dropped}
