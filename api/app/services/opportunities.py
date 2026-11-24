"""공고 정규화 결과 검증과 저장(인계서 10.6절, 11.4절).

LLM이 정리한 공고 정보는 페이지 본문과 맞춰 본 뒤에만 저장한다(2.3절 원칙).
- 날짜: 그 월·일 숫자가 본문에 있어야 한다. 오늘 기준 1년 전~2년 뒤 밖이면 버린다.
- 주최·혜택·요약: 본문에 없는 숫자가 들어 있으면 버리거나 그 문장을 지운다. 주최는 본문에 있어야 한다.
"""

import re
from datetime import date, timedelta
from typing import Any
from uuid import UUID

from app.db import as_json
from app.llm.schemas import OpportunityExtract
from app.llm.validators import (
    drop_unsupported_sentences,
    normalize_ws,
    numbers_supported,
)

DATE_FIELDS = (
    "apply_start",
    "apply_deadline",
    "result_announce_on",
    "activity_start",
    "activity_end",
)


def _date_supported(d: date, text: str, today: date) -> bool:
    if d < today - timedelta(days=366) or d > today + timedelta(days=730):
        return False
    # "2026.12.4"를 소수로 읽지 않게 숫자 덩어리를 따로 뽑는다.
    nums = {n.lstrip("0") or "0" for n in re.findall(r"\d+", text)} | set(re.findall(r"\d+", text))
    month, day = str(d.month), str(d.day)
    return (month in nums or f"{d.month:02d}" in nums) and (day in nums or f"{d.day:02d}" in nums)


def clean_opportunity(
    ext: OpportunityExtract, page_text: str, today: date
) -> dict[str, Any] | None:
    """저장할 값만 남긴다. 공고가 아니거나 제목이 없으면 None."""
    if not ext.is_opportunity or not ext.title.strip():
        return None
    data = ext.model_dump()
    for key in DATE_FIELDS:
        value = data[key]
        if value is not None and not _date_supported(value, page_text, today):
            data[key] = None
    if (
        data["apply_start"]
        and data["apply_deadline"]
        and data["apply_start"] > data["apply_deadline"]
    ):
        data["apply_start"] = None
    src = normalize_ws(page_text)
    org = data["organizer"].strip()
    data["organizer"] = org if org and normalize_ws(org) in src else None
    for key in ("benefits", "location"):
        v = data[key].strip()
        data[key] = v if v and numbers_supported(v, page_text) else None
    data["summary"], _ = drop_unsupported_sentences(data["summary"], page_text)
    elig = data["eligibility"]
    elig["grades"] = sorted({g for g in elig["grades"] if 1 <= g <= 6})
    elig["majors"] = [m for m in elig["majors"] if m and normalize_ws(m) in src][:10]
    data["tags"] = list(dict.fromkeys(t.strip() for t in data["tags"] if t.strip()))[:8]
    data["title"] = data["title"].strip()[:200]
    return data


async def upsert_opportunity(
    db, url: str, data: dict[str, Any], *, created_by: UUID | None = None
) -> UUID:
    """같은 URL은 갱신만 한다. db는 SystemDB(수집) 또는 UserDB.system."""
    params = dict(
        url=url,
        site=url.split("/")[2] if "://" in url else None,
        title=data["title"],
        organizer=data["organizer"],
        category=data["category"],
        summary=data["summary"],
        eligibility=as_json(data["eligibility"]),
        benefits=data["benefits"],
        apply_start=data["apply_start"],
        apply_deadline=data["apply_deadline"],
        result_announce_on=data["result_announce_on"],
        activity_start=data["activity_start"],
        activity_end=data["activity_end"],
        location=data["location"],
        is_online=data["is_online"],
        tags=data["tags"],
        created_by=created_by,
    )
    conflict = (
        "(source_url) where created_by is null"
        if created_by is None
        else "(source_url, created_by) where created_by is not null"
    )
    return await db.scalar(
        f"""insert into opportunities (source_url, source_site, title, organizer, category, summary,
              eligibility, benefits, apply_start, apply_deadline, result_announce_on, activity_start,
              activity_end, location, is_online, tags, created_by, is_active, fetched_at)
            values (:url, :site, :title, :organizer, cast(:category as opportunity_category),
              :summary, cast(:eligibility as jsonb), :benefits, :apply_start, :apply_deadline,
              :result_announce_on, :activity_start, :activity_end, :location, :is_online, :tags,
              :created_by,
              coalesce(:apply_deadline >= current_date, true), now())
            on conflict {conflict} do update set
              title = excluded.title, organizer = excluded.organizer, category = excluded.category,
              summary = excluded.summary, eligibility = excluded.eligibility,
              benefits = excluded.benefits, apply_start = excluded.apply_start,
              apply_deadline = excluded.apply_deadline,
              result_announce_on = excluded.result_announce_on,
              activity_start = excluded.activity_start, activity_end = excluded.activity_end,
              location = excluded.location, is_online = excluded.is_online, tags = excluded.tags,
              is_active = excluded.is_active, fetched_at = now()
            returning id""",
        **params,
    )


def opportunity_text(o: dict) -> str:
    """임베딩·키워드 비교에 쓰는 공고 글."""
    return "\n".join(
        p
        for p in [
            o["title"],
            o.get("organizer") or "",
            o.get("summary") or "",
            ", ".join(o.get("tags") or []),
        ]
        if p
    )


async def deactivate_expired(db) -> int:
    return await db.execute(
        """update opportunities set is_active = false
           where is_active and apply_deadline is not null and apply_deadline < current_date"""
    )
