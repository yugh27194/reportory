"""LLM 출력 서버 검증(인계서 10.2절 '출력 후 서버 검증').

"원문에 없는 사실을 만들지 않는다"를 프롬프트가 아니라 코드로 강제한다.
"""

import re
from dataclasses import dataclass, field
from datetime import date
from uuid import UUID

from app.llm.schemas import DETAILS_KEYS, ExtractionResult, ItemCandidate

MIN_CONFIDENCE = 0.5
DATE_RANGE_YEARS = 10

_WS = re.compile(r"\s+")
_NUM = re.compile(r"\d+(?:[.,]\d+)*")
_SENTENCE = re.compile(r"(?<=[.!?。])\s+")


def normalize_ws(text: str) -> str:
    return _WS.sub(" ", text).strip()


def quote_in_source(quote: str, source: str) -> bool:
    q = normalize_ws(quote)
    return bool(q) and q in normalize_ws(source)


def numbers_in(text: str) -> list[str]:
    return [n.replace(",", "") for n in _NUM.findall(text)]


def numbers_supported(text: str, source: str) -> bool:
    """text 안의 모든 숫자가 source에 그대로 있어야 한다."""
    available = set(numbers_in(source))
    return all(n in available for n in numbers_in(text))


def drop_unsupported_sentences(text: str, source: str) -> tuple[str, int]:
    """근거에 없는 숫자가 든 문장을 지우고, 지운 문장 수를 돌려준다."""
    kept, dropped = [], 0
    for sentence in _SENTENCE.split(text.strip()) if text.strip() else []:
        if numbers_supported(sentence, source):
            kept.append(sentence)
        else:
            dropped += 1
    return " ".join(kept), dropped


def _shift_years(d: date, years: int) -> date:
    try:
        return d.replace(year=d.year + years)
    except ValueError:  # 2월 29일
        return d.replace(year=d.year + years, day=28)


def date_in_range(value: date, reference: date) -> bool:
    return (
        _shift_years(reference, -DATE_RANGE_YEARS)
        <= value
        <= _shift_years(reference, DATE_RANGE_YEARS)
    )


@dataclass
class ValidationReport:
    dropped_candidates: int = 0
    dropped_values: int = 0
    dropped_application_updates: int = 0
    dropped_followups: int = 0
    reasons: list[str] = field(default_factory=list)

    def note(self, reason: str) -> None:
        self.reasons.append(reason)


def clean_candidate(
    cand: ItemCandidate,
    source: str,
    reference_date: date,
    known_item_ids: set[UUID],
    report: ValidationReport,
) -> ItemCandidate | None:
    """후보 하나를 검증한다. 버려야 하면 None, 일부 값만 틀리면 그 값만 지운 사본을 돌려준다."""
    if cand.confidence < MIN_CONFIDENCE:
        report.note("low_confidence")
        return None
    if not quote_in_source(cand.quote, source):
        report.note("quote_not_in_source")
        return None
    if cand.action in ("update", "link"):
        if cand.target_item_id is None or cand.target_item_id not in known_item_ids:
            report.note("unknown_target_item")
            return None
    elif cand.target_item_id is not None:
        cand = cand.model_copy(update={"target_item_id": None})

    data = cand.model_dump()

    metrics = []
    for m in cand.metrics:
        if numbers_in(m.value) and numbers_supported(m.value, source):
            metrics.append(m.model_dump())
        elif not numbers_in(m.value) and normalize_ws(m.value) in normalize_ws(source):
            metrics.append(m.model_dump())
        else:
            report.dropped_values += 1
    data["metrics"] = metrics

    allowed = DETAILS_KEYS.get(cand.type, ())
    details = {}
    for key, value in cand.details.items():
        if key not in allowed or value is None:
            continue
        if not numbers_supported(str(value), source):
            report.dropped_values += 1
            continue
        details[key] = value
    data["details"] = details

    for key in ("start_date", "end_date"):
        value = data[key]
        if value is not None and not date_in_range(value, reference_date):
            data[key] = None
            report.dropped_values += 1
    if (
        data["end_date"] is not None
        and data["end_date"] > reference_date
        and not data["is_ongoing"]
    ):
        data["end_date"] = None
        report.dropped_values += 1

    summary, dropped = drop_unsupported_sentences(data["summary_append"], source)
    data["summary_append"] = summary
    report.dropped_values += dropped

    data["skills"] = [s.strip() for s in data["skills"] if s and s.strip()]
    return ItemCandidate.model_validate(data)


def validate_extraction(
    result: ExtractionResult,
    source: str,
    reference_date: date,
    known_item_ids: set[UUID],
    open_application_ids: set[UUID],
) -> tuple[ExtractionResult, ValidationReport, dict[int, int]]:
    """추출 결과 전체를 검증한다.

    돌려주는 dict는 원래 후보 index → 검증 후 index 대응이다. 후속 질문의
    "candidate:<index>" 대상을 다시 맞추는 데 쓴다.
    """
    report = ValidationReport()
    items: list[ItemCandidate] = []
    index_map: dict[int, int] = {}
    if result.is_relevant:
        for i, cand in enumerate(result.items):
            cleaned = clean_candidate(cand, source, reference_date, known_item_ids, report)
            if cleaned is None:
                report.dropped_candidates += 1
                continue
            index_map[i] = len(items)
            items.append(cleaned)

    updates = []
    for upd in result.application_updates if result.is_relevant else []:
        if (
            upd.confidence < MIN_CONFIDENCE
            or upd.application_id not in open_application_ids
            or not quote_in_source(upd.quote, source)
        ):
            report.dropped_application_updates += 1
            continue
        if upd.result_date is not None and not date_in_range(upd.result_date, reference_date):
            upd = upd.model_copy(update={"result_date": None})
        updates.append(upd)

    followups = []
    for f in result.followups if result.is_relevant else []:
        kind, _, ref = f.target.partition(":")
        if kind == "candidate" and ref.isdigit() and int(ref) in index_map:
            followups.append(f.model_copy(update={"target": f"candidate:{index_map[int(ref)]}"}))
        elif kind == "item":
            try:
                ok = UUID(ref) in known_item_ids
            except ValueError:
                ok = False
            if ok:
                followups.append(f)
            else:
                report.dropped_followups += 1
        else:
            report.dropped_followups += 1

    cleaned = ExtractionResult(
        is_relevant=result.is_relevant,
        entry_summary=drop_unsupported_sentences(result.entry_summary, source)[0],
        items=items,
        application_updates=updates,
        followups=followups[:3],
    )
    return cleaned, report, index_map
