"""증빙과 항목 맞추기(인계서 10.10절, 11.7절)."""

from datetime import date
from difflib import SequenceMatcher
from typing import Any
from uuid import UUID

from app.db import UserDB, as_json
from app.errors import not_found
from app.llm.schemas import EvidenceExtract
from app.services.items import add_source, get_item
from app.services.skills import normalize_skill

# 증빙 종류 → 맞춰 볼 항목 유형
KIND_ITEM_TYPES: dict[str, tuple[str, ...]] = {
    "language_score": ("language_test",),
    "certificate": ("certification",),
    "award_certificate": ("award",),
    "completion_certificate": ("activity", "experience", "education", "project"),
    "other": (),
}

# 증빙에서 새 항목을 만들 때의 유형
KIND_NEW_TYPE = {
    "language_score": "language_test",
    "certificate": "certification",
    "award_certificate": "award",
    "completion_certificate": "activity",
}

MATCH_MIN_TITLE = 0.6
DATE_WINDOW_DAYS = 30

# 충돌·빈칸 채우기에 쓰는 필드: 필드 이름 → (항목 쪽 위치, 증빙 값 이름)
FIELDS_BY_TYPE: dict[str, dict[str, tuple[tuple[str, str], str]]] = {
    "language_test": {
        "score": (("details", "score"), "score"),
        "test_date": (("details", "test_date"), "issued_on"),
        "valid_until": (("details", "valid_until"), "expires_on"),
    },
    "certification": {
        "issuer": (("details", "issuer"), "issuer"),
        "acquired_on": (("column", "start_date"), "issued_on"),
    },
    "award": {
        "rank": (("details", "rank"), "award_rank"),
        "host": (("details", "host"), "issuer"),
        "awarded_on": (("column", "end_date"), "issued_on"),
    },
}
FIELD_LABELS = {
    "score": "점수",
    "test_date": "응시일",
    "valid_until": "유효기간",
    "issuer": "발급기관",
    "acquired_on": "취득일",
    "rank": "순위",
    "host": "주최",
    "awarded_on": "수상일",
}


def title_similarity(a: str | None, b: str | None) -> float:
    na, nb = normalize_skill(a or ""), normalize_skill(b or "")
    if not na or not nb:
        return 0.0
    if na in nb or nb in na:
        return max(0.9, SequenceMatcher(None, na, nb).ratio())
    return SequenceMatcher(None, na, nb).ratio()


def _as_date(v: Any) -> date | None:
    if isinstance(v, date):
        return v
    if isinstance(v, str):
        try:
            return date.fromisoformat(v[:10])
        except ValueError:
            return None
    return None


def match_score(item: dict, ext: EvidenceExtract) -> float:
    """제목 유사도 + 발급기관 일치(0.2) + 날짜 30일 이내(0.2)."""
    candidates = [item["title"], item.get("title_en"), (item.get("details") or {}).get("test")]
    title = max(title_similarity(c, ext.title) for c in candidates)
    if title < MATCH_MIN_TITLE:
        return 0.0
    score = title
    details = item.get("details") or {}
    issuer_values = [item.get("organization"), details.get("issuer"), details.get("host")]
    if ext.issuer and any(title_similarity(v, ext.issuer) >= 0.8 for v in issuer_values if v):
        score += 0.2
    if ext.issued_on:
        dates = [item.get("start_date"), item.get("end_date"), details.get("test_date")]
        if any(
            (d := _as_date(v)) and abs((d - ext.issued_on).days) <= DATE_WINDOW_DAYS for v in dates
        ):
            score += 0.2
    return score


def _norm_value(v: Any) -> str:
    return normalize_skill(str(v)) if v is not None else ""


def compare(item: dict, ext: EvidenceExtract) -> tuple[list[dict], list[dict]]:
    """(충돌, 빈칸 채우기) 목록을 돌려준다. 값은 화면에 그대로 보여 줄 수 있게 문자열로 둔다."""
    conflicts, fills = [], []
    for field, ((where, key), ext_name) in FIELDS_BY_TYPE.get(item["type"], {}).items():
        ev = getattr(ext, ext_name)
        if ev is None or ev == "":
            continue
        current = (item.get("details") or {}).get(key) if where == "details" else item.get(key)
        ev_s = ev.isoformat() if isinstance(ev, date) else str(ev)
        cur_s = current.isoformat() if isinstance(current, date) else current
        if cur_s in (None, ""):
            fills.append({"field": field, "label": FIELD_LABELS[field], "evidence_value": ev_s})
        elif _norm_value(cur_s) != _norm_value(ev_s):
            conflicts.append(
                {
                    "field": field,
                    "label": FIELD_LABELS[field],
                    "item_value": str(cur_s),
                    "evidence_value": ev_s,
                }
            )
    return conflicts, fills


async def best_item(db: UserDB, ext: EvidenceExtract) -> tuple[dict | None, float]:
    types = KIND_ITEM_TYPES.get(ext.kind, ())
    if not types or not ext.title:
        return None, 0.0
    rows = await db.all(
        """select id, type, title, title_en, organization, start_date, end_date, details
           from items where user_id = :user_id and status in ('approved', 'proposed')
             and type = any(cast(:types as item_type[]))""",
        types=list(types),
    )
    scored = sorted(((match_score(r, ext), r) for r in rows), key=lambda x: x[0], reverse=True)
    if scored and scored[0][0] > 0:
        return scored[0][1], scored[0][0]
    return None, 0.0


async def apply_attach(db: UserDB, payload: dict, edited: dict | None) -> dict:
    """attach_evidence 승인: 증빙을 항목에 연결하고, 고른 쪽 값으로 항목을 고친다."""
    evidence_id = UUID(payload["evidence_id"])
    item_id = UUID(str((edited or {}).get("item_id") or payload["item_id"]))
    item = await get_item(db, item_id, statuses=("approved", "proposed"))
    ev = await db.one(
        "select id, extracted from evidence where id = :id and user_id = :user_id", id=evidence_id
    )
    if ev is None:
        raise not_found("증빙을 찾을 수 없다.")
    resolutions: dict[str, str] = (edited or {}).get("resolutions") or {}
    fields = FIELDS_BY_TYPE.get(item["type"], {})
    updates: dict[str, Any] = {}
    for c in payload.get("conflicts", []):
        if resolutions.get(c["field"]) == "evidence" and c["field"] in fields:
            updates[c["field"]] = c["evidence_value"]
    skip_fills = set((edited or {}).get("skip_fills") or [])
    for f in payload.get("fills", []):
        if f["field"] in fields and f["field"] not in skip_fills:
            updates[f["field"]] = f["evidence_value"]
    details = dict(item["details"])
    columns: dict[str, Any] = {}
    for field, value in updates.items():
        (where, key), _ = fields[field]
        if where == "details":
            details[key] = value
        else:
            columns[key] = _as_date(value)
    sets = ["details = cast(:details as jsonb)"] + [f"{k} = :{k}" for k in columns]
    await db.execute(
        f"update items set {', '.join(sets)} where id = :id and user_id = :user_id",
        id=item_id,
        details=as_json(details),
        **columns,
    )
    await db.execute(
        "update evidence set item_id = :item_id where id = :id and user_id = :user_id",
        id=evidence_id,
        item_id=item_id,
    )
    await add_source(db, item_id, evidence_id=evidence_id)
    return {**payload, "item_id": str(item_id), "applied": sorted(updates)}
