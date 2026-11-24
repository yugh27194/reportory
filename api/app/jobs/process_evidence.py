"""증빙 분류와 추출(인계서 10.10절)."""

from uuid import UUID

from app.db import UserDB, as_json
from app.llm.calls import call_logger
from app.llm.client import Attachment, get_llm
from app.llm.schemas import EvidenceExtract
from app.llm.validators import numbers_supported
from app.services.evidence import KIND_NEW_TYPE, best_item, compare
from app.services.privacy import scrub, scrub_values
from app.services.skills import normalize_skill
from app.services.test_validity import estimate_expiry
from app.services.text_extract import pdf_text
from app.storage import get_storage

MAX_TEXT = 20000
# 증빙은 한 장짜리라 글자가 짧다. 이보다 짧으면 스캔본으로 보고 파일을 LLM에 넘긴다.
EVIDENCE_TEXT_MIN = 30


def _verify_against_text(ext: EvidenceExtract, text: str) -> EvidenceExtract:
    """글자로 읽은 경우, 숫자가 든 값은 원문에 그 숫자가 있어야 한다(지어내지 않는다)."""
    data = ext.model_dump()
    for key in ("score", "award_rank", "title", "issuer"):
        if data[key] and not numbers_supported(str(data[key]), text):
            data[key] = None
    for key in ("issued_on", "expires_on"):
        d = data[key]
        if d and str(d.year) not in text:
            data[key] = None
    return EvidenceExtract.model_validate(data)


async def run(db: UserDB, payload: dict) -> dict:
    evidence_id = UUID(payload["evidence_id"])
    ev = await db.one(
        """select id, item_id, storage_path, file_name, mime_type from evidence
           where id = :id and user_id = :user_id""",
        id=evidence_id,
    )
    if ev is None:
        return {"skipped": "evidence_deleted"}

    # 멱등: 이 증빙에서 나온 대기 제안을 먼저 지운다.
    await db.execute(
        """delete from proposals where user_id = :user_id and evidence_id = :id
             and status = 'pending'""",
        id=evidence_id,
    )
    await db.execute(
        """update items set status = 'rejected' where user_id = :user_id and status = 'proposed'
             and id in (select item_id from item_sources
                        where user_id = :user_id and evidence_id = :id)""",
        id=evidence_id,
    )

    data = await get_storage().get("evidence", ev["storage_path"])
    text = pdf_text(data) if ev["mime_type"] == "application/pdf" else ""
    attachments = None
    if len(text) < EVIDENCE_TEXT_MIN:
        attachments = [Attachment(ev["mime_type"], data)]
    ext = await get_llm().complete_json(
        "process_evidence",
        "process_evidence",
        {"FILE_NAME": ev["file_name"], "TEXT": text},
        EvidenceExtract,
        "extract",
        user_id=db.user_id,
        log_call=call_logger(db),
        attachments=attachments,
    )
    if attachments is None:
        ext = _verify_against_text(ext, text)
    ext = EvidenceExtract.model_validate(scrub_values(ext.model_dump()))

    extracted = ext.model_dump(mode="json")
    expires_on = ext.expires_on
    if ext.kind == "language_score" and expires_on is None:
        expires_on = estimate_expiry(ext.title, ext.issued_on)
        if expires_on:
            extracted["expires_on_estimated"] = True
            ext = ext.model_copy(update={"expires_on": expires_on})

    await db.execute(
        """update evidence set kind = cast(:kind as evidence_kind), status = 'processed',
             ocr_text = :text, extracted = cast(:extracted as jsonb), issued_on = :issued,
             expires_on = :expires
           where id = :id and user_id = :user_id""",
        id=evidence_id,
        kind=ext.kind,
        text=scrub(text[:MAX_TEXT]) or None,
        extracted=as_json(extracted),
        issued=ext.issued_on,
        expires=expires_on,
    )

    proposals = 0
    if ev["item_id"]:
        target = await db.one(
            """select id, type, title, title_en, organization, start_date, end_date, details
               from items where id = :id and user_id = :user_id
                 and status in ('approved', 'proposed')""",
            id=ev["item_id"],
        )
    else:
        target, _ = await best_item(db, ext)

    if target is None and ext.kind in KIND_NEW_TYPE and ext.title:
        target = await _create_item_from_evidence(db, ext, evidence_id)
        proposals += 1

    if target is not None:
        conflicts, fills = compare(target, ext)
        await _proposal(
            db,
            "attach_evidence",
            {
                "evidence_id": str(evidence_id),
                "item_id": str(target["id"]),
                "conflicts": conflicts,
                "fills": fills,
            },
            evidence_id,
            target["id"],
            ext.confidence,
        )
        proposals += 1

    if ext.kind in ("completion_certificate", "award_certificate") and ext.title:
        proposals += await _completion_proposals(db, ext, evidence_id)

    if proposals:
        await db.execute(
            """insert into notifications (user_id, type, title, link, ref_id)
               values (:user_id, 'proposals_ready', '증빙을 읽고 연결 제안을 만들었다.', '/review', :id)
               on conflict do nothing""",
            id=evidence_id,
        )
    return {"kind": ext.kind, "proposals": proposals, "matched": target is not None}


async def _proposal(db, kind, payload, evidence_id, item_id, confidence, application_id=None):
    await db.execute(
        """insert into proposals (user_id, kind, payload, item_id, evidence_id, application_id,
             confidence)
           values (:user_id, cast(:kind as proposal_kind), cast(:payload as jsonb), :item_id,
             :evidence_id, :application_id, :confidence)""",
        kind=kind,
        payload=as_json(payload),
        item_id=item_id,
        evidence_id=evidence_id,
        application_id=application_id,
        confidence=confidence,
    )


async def _create_item_from_evidence(db: UserDB, ext: EvidenceExtract, evidence_id: UUID) -> dict:
    item_type = KIND_NEW_TYPE[ext.kind]
    details: dict = {}
    start = end = None
    if item_type == "language_test":
        details = {"test": ext.title}
    elif item_type == "certification":
        details = {"issuer": ext.issuer} if ext.issuer else {}
        start = ext.issued_on
    elif item_type == "award":
        details = {"host": ext.issuer} if ext.issuer else {}
        end = ext.issued_on
    else:
        end = ext.issued_on
    row = await db.one(
        """insert into items (user_id, type, status, title, organization, start_date, end_date,
             details)
           values (:user_id, cast(:type as item_type), 'proposed', :title, :org, :start, :end,
             cast(:details as jsonb))
           returning id, type, title, title_en, organization, start_date, end_date, details""",
        type=item_type,
        title=ext.title[:200],
        org=ext.issuer if item_type in ("activity", "certification") else None,
        start=start,
        end=end,
        details=as_json(details),
    )
    await db.execute(
        """insert into item_sources (item_id, user_id, evidence_id)
           values (:item_id, :user_id, :evidence_id)""",
        item_id=row["id"],
        evidence_id=evidence_id,
    )
    await _proposal(
        db, "create_item", {"item_id": str(row["id"])}, evidence_id, row["id"], ext.confidence
    )
    return row


async def _completion_proposals(db: UserDB, ext: EvidenceExtract, evidence_id: UUID) -> int:
    """활동 중(active)인 지원과 제목이 맞는 수료증·상장이면 completed 전이를 제안한다."""
    apps = await db.all(
        "select id, title from applications where user_id = :user_id and status = 'active'"
    )
    n = 0
    target = normalize_skill(ext.title or "")
    for app in apps:
        title = normalize_skill(app["title"])
        if target and (target in title or title in target):
            await _proposal(
                db,
                "application_update",
                {
                    "application_id": str(app["id"]),
                    "to_status": "completed",
                    "result_date": ext.issued_on.isoformat() if ext.issued_on else None,
                    "quote": None,
                },
                evidence_id,
                None,
                ext.confidence,
                application_id=app["id"],
            )
            n += 1
    return n


async def on_final_failure(db: UserDB, payload: dict) -> None:
    await db.execute(
        "update evidence set status = 'failed' where id = :id and user_id = :user_id",
        id=UUID(payload["evidence_id"]),
    )
