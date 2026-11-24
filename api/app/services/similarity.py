"""임베딩 유사도(인계서 10.2절 KNOWN_ITEMS 선택, 중복 의심 6번).

임베딩을 쓸 수 없으면(제공사 미설정, API 오류) 규칙 기반으로 물러나고 추출은 계속한다.
"""

import logging
import math
from uuid import UUID

from app.db import UserDB
from app.embeddings import embed
from app.llm.schemas import ItemCandidate
from app.services.skills import normalize_skill

log = logging.getLogger("reportory.similarity")

DUPLICATE_THRESHOLD = 0.92
MAX_COMPARE_TITLES = 200


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


async def safe_embed(texts: list[str]) -> list[list[float]] | None:
    if not texts:
        return []
    try:
        return await embed(texts)
    except Exception as exc:  # noqa: BLE001 - 임베딩 실패(API 오류 포함)로 추출을 멈추지 않는다
        log.warning("embedding unavailable: %s", type(exc).__name__)
        return None


async def find_duplicates(db: UserDB, cands: list[ItemCandidate]) -> list[UUID | None]:
    """create 후보마다 같은 유형 기존 항목 중 중복 의심 항목 id를 찾는다.

    정규화한 제목이 같으면 바로 중복으로 보고, 나머지는 제목 임베딩 코사인 유사도 0.92 이상을 찾는다.
    """
    result: list[UUID | None] = [None] * len(cands)
    if not cands:
        return result
    types = sorted({c.type for c in cands})
    rows = await db.all(
        f"""select id, type, title from items
            where user_id = :user_id and status in ('approved', 'proposed')
              and type = any(cast(:types as item_type[]))
            order by updated_at desc limit {MAX_COMPARE_TITLES}""",
        types=types,
    )
    pending: list[int] = []
    for i, c in enumerate(cands):
        target = normalize_skill(c.title)
        exact = next(
            (
                r["id"]
                for r in rows
                if r["type"] == c.type and normalize_skill(r["title"]) == target
            ),
            None,
        )
        if exact:
            result[i] = exact
        elif any(r["type"] == c.type for r in rows):
            pending.append(i)
    if not pending:
        return result

    titles = [cands[i].title for i in pending] + [r["title"] for r in rows]
    vectors = await safe_embed(titles)
    if not vectors:
        return result
    cand_vecs, row_vecs = vectors[: len(pending)], vectors[len(pending) :]
    for i, vec in zip(pending, cand_vecs, strict=True):
        best, best_id = 0.0, None
        for r, rv in zip(rows, row_vecs, strict=True):
            if r["type"] != cands[i].type:
                continue
            score = cosine(vec, rv)
            if score > best:
                best, best_id = score, r["id"]
        if best >= DUPLICATE_THRESHOLD:
            result[i] = best_id
    return result
