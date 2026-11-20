"""후속 질문 답변 처리(인계서 10.3절). 답변을 근거로 update_item 제안을 만든다."""

from datetime import date
from uuid import UUID

from app.db import UserDB, as_json
from app.jobs.extract_entry import update_patch
from app.llm.calls import call_logger
from app.llm.client import get_llm
from app.llm.schemas import ItemCandidate
from app.llm.validators import ValidationReport, clean_candidate
from app.services.skills import skills_of


async def run(db: UserDB, payload: dict) -> dict:
    followup_id = UUID(payload["followup_id"])
    f = await db.one(
        """select id, item_id, question, answer, status from followup_questions
           where id = :id and user_id = :user_id""",
        id=followup_id,
    )
    if f is None or f["status"] != "answered" or not f["answer"]:
        return {"skipped": "not_answered"}
    item = await db.one(
        """select id, type, title, organization, role, start_date, end_date, is_ongoing, summary,
                  metrics, details
           from items where id = :id and user_id = :user_id""",
        id=f["item_id"],
    )
    if item is None:
        return {"skipped": "item_missing"}

    # 멱등: 같은 질문에서 나온 대기 제안을 지운다.
    await db.execute(
        """delete from proposals where user_id = :user_id and status = 'pending'
             and payload ->> 'followup_id' = cast(:fid as text)""",
        fid=str(followup_id),
    )

    item_ctx = {**item, "id": str(item["id"]), "skills": await skills_of(db, item["id"])}
    cand = await get_llm().complete_json(
        "answer_followup",
        "answer_followup",
        {"ITEM": item_ctx, "QUESTION": f["question"], "ANSWER": f["answer"]},
        ItemCandidate,
        "extract",
        user_id=db.user_id,
        log_call=call_logger(db),
    )
    cand = cand.model_copy(
        update={"action": "update", "target_item_id": item["id"], "type": item["type"]}
    )
    report = ValidationReport()
    cleaned = clean_candidate(cand, f["answer"], date.today(), {item["id"]}, report)
    if cleaned is None:
        return {"proposals": 0, "dropped": report.reasons}
    await db.execute(
        """insert into proposals (user_id, kind, payload, item_id, confidence, quote)
           values (:user_id, 'update_item', cast(:payload as jsonb), :item_id, :confidence, :quote)""",
        payload=as_json(
            {
                "item_id": str(item["id"]),
                "patch": update_patch(cleaned),
                "followup_id": str(followup_id),
            }
        ),
        item_id=item["id"],
        confidence=cleaned.confidence,
        quote=cleaned.quote,
    )
    return {"proposals": 1}
