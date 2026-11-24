"""이력서 PDF·DOCX 가져오기(인계서 10.9절)."""

from datetime import date
from uuid import UUID

from app.db import UserDB
from app.importers.common import ImportResult, save_candidates
from app.llm.calls import call_logger
from app.llm.client import Attachment, get_llm
from app.llm.schemas import ExtractionResult
from app.llm.validators import validate_extraction
from app.services.text_extract import SCANNED_THRESHOLD, docx_text, pdf_text

SCANNED_MAX_CONFIDENCE = 0.7  # 글자로 대조할 수 없는 스캔본은 일괄 승인되지 않게 낮춘다
MAX_TEXT = 30000


async def run_resume(db: UserDB, import_id: UUID, data: bytes, mime: str) -> ImportResult:
    result = ImportResult()
    text = pdf_text(data) if mime == "application/pdf" else docx_text(data)
    text = text[:MAX_TEXT]
    attachments = None
    scanned = len(text) < SCANNED_THRESHOLD
    if scanned and mime == "application/pdf":
        attachments = [Attachment(mime, data)]
    elif scanned and not text:
        result.skipped.append("글자를 읽을 수 없는 문서")
        return result

    raw = await get_llm().complete_json(
        "import_resume",
        "import_resume",
        {"ENTRY_DATE": date.today().isoformat(), "ENTRY": text},
        ExtractionResult,
        "extract",
        user_id=db.user_id,
        log_call=call_logger(db),
        attachments=attachments,
    )
    # 스캔본은 원문 글자가 없으므로, 숫자가 모델이 읽었다고 한 인용 안에 있는지만 확인한다.
    source = text if not attachments else "\n".join(c.quote for c in raw.items)
    cleaned, report, _ = validate_extraction(raw, source, date.today(), set(), set())
    cands = cleaned.items
    if attachments:
        cands = [
            c.model_copy(update={"confidence": min(c.confidence, SCANNED_MAX_CONFIDENCE)})
            for c in cands
        ]
        result.notes["scanned"] = True
    result.dropped += report.dropped_candidates
    await save_candidates(db, import_id, cands, result)
    return result
