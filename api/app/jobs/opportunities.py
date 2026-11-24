"""공고 수집(collect_opportunities)과 URL로 공고 추가(fetch_opportunity_url). 인계서 11.4절."""

import logging
from datetime import datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from app.config import get_settings
from app.crawler.fetch import FetchError, Page, fetch_page
from app.db import SystemDB, UserDB
from app.embeddings import embed
from app.llm.calls import call_logger, system_call_logger
from app.llm.client import CallLogger, LLMError, get_llm
from app.llm.schemas import OpportunityExtract
from app.services.jobs import enqueue
from app.services.opportunities import (
    clean_opportunity,
    deactivate_expired,
    opportunity_text,
    upsert_opportunity,
)

log = logging.getLogger("reportory.opportunities")
KST = ZoneInfo("Asia/Seoul")

BASE_QUERIES = [
    "대학생 공모전 모집",
    "대학생 해커톤 참가자 모집",
    "학부연구생 모집",
    "대학생 연구 인턴 모집",
    "대학생 대외활동 모집",
    "대학생 인턴십 모집",
    "대학생 장학생 선발 공고",
]


def today_kst():
    return datetime.now(KST).date()


async def build_queries(db: SystemDB) -> list[str]:
    """고정 검색어 + 사용자 관심 키워드 상위 20개(인계서 11.4절). 연도를 붙인다."""
    year = today_kst().year
    rows = await db.all(
        """select kw, count(*) as n from (
             select unnest(interests || target_roles) as kw from profiles) k
           where char_length(kw) between 2 and 20
           group by kw order by n desc, kw limit 20"""
    )
    queries = [f"{q} {year}" for q in BASE_QUERIES]
    queries += [f"{r['kw']} 대학생 모집 {year}" for r in rows]
    return queries[: get_settings().search_max_queries]


async def normalize_page(page: Page, log_call: CallLogger) -> dict | None:
    ext = await get_llm().complete_json(
        "normalize_opportunity",
        "normalize_opportunity",
        {
            "URL": page.url,
            "TODAY": today_kst().isoformat(),
            "PAGE_TITLE": page.title,
            "PAGE": page.text,
        },
        OpportunityExtract,
        "light",
        log_call=log_call,
    )
    return clean_opportunity(ext, page.text, today_kst())


async def _embed_opportunity(db: SystemDB, opp_id: UUID, data: dict) -> None:
    vectors = await embed([opportunity_text(data)])
    if vectors:
        await db.execute(
            "update opportunities set embedding = cast(:v as vector) where id = :id",
            id=opp_id,
            v=str(vectors[0]),
        )


async def collect(db: SystemDB, payload: dict) -> dict:
    s = get_settings()
    stats = {"deactivated": await deactivate_expired(db), "queries": 0, "found": 0}
    stats.update(saved=0, not_opportunity=0, skipped=0, fresh=0)
    log_call = system_call_logger()
    llm = get_llm()
    urls: list[str] = []
    for q in payload.get("queries") or await build_queries(db):
        try:
            hits = await llm.search_web(q, log_call=log_call)
        except LLMError as exc:
            if exc.permanent:
                raise
            log.warning("search failed: %s", type(exc).__name__)
            continue
        stats["queries"] += 1
        urls += [h["url"] for h in hits if h["url"] not in urls]
    stats["found"] = len(urls)
    fresh = {
        r["source_url"]
        for r in await db.all(
            """select source_url from opportunities
               where created_by is null and source_url = any(:urls)
                 and fetched_at > now() - make_interval(days => :d)""",
            urls=urls,
            d=s.crawler_refetch_days,
        )
    }
    stats["fresh"] = len(fresh)
    done_today = await db.scalar(
        """select count(*) from opportunities
           where created_by is null and fetched_at >= date_trunc('day', now())"""
    )
    budget = max(0, s.crawler_daily_page_limit - (done_today or 0))
    for url in [u for u in urls if u not in fresh][:budget]:
        try:
            page = await fetch_page(url)
            data = await normalize_page(page, log_call)
        except FetchError:
            stats["skipped"] += 1
            continue
        except LLMError as exc:
            if exc.permanent:
                raise
            stats["skipped"] += 1
            continue
        if data is None:
            stats["not_opportunity"] += 1
            continue
        opp_id = await upsert_opportunity(db, url, data)
        await _embed_opportunity(db, opp_id, data)
        stats["saved"] += 1
    return stats


async def fetch_url(db: UserDB, payload: dict) -> dict:
    """사용자가 넣은 URL을 읽어 본인에게만 보이는 공고로 저장한다."""
    page = await fetch_page(payload["url"])
    data = await normalize_page(page, call_logger(db))
    if data is None:
        raise FetchError(
            "모집 공고 페이지로 보이지 않는다. 공고 한 건의 상세 페이지 주소를 넣는다."
        )
    opp_id = await upsert_opportunity(db.system, payload["url"], data, created_by=db.user_id)
    await _embed_opportunity(db.system, opp_id, data)
    await enqueue(db, "score_recommendations", {"only_opportunity_id": str(opp_id)})
    return {"opportunity_id": str(opp_id), "title": data["title"]}
