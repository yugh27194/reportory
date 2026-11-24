"""추천 점수 계산(인계서 10.7절).

score = 0.55·sim + 0.20·gap + 0.15·pref + 0.10·urgency (가중치: reco_config.py)
- sim: 프로필 임베딩과 공고 임베딩의 코사인 유사도. 임베딩이 없으면 키워드 겹침으로 대신한다.
- gap: 목표 대비 부족한 경험을 채우는 공고면 1.
- pref: 분류별 피드백 선호도, 불합격만 반복된 분류는 감점.
- urgency: 마감이 14일 안이면 1.
"""

import math
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any
from uuid import UUID

from app.services import reco_config as C

INTERNSHIP_CATS = {"internship"}
RESEARCH_CATS = {"research_internship"}


@dataclass
class UserContext:
    goal: str
    grade: int | None
    major: str | None
    interests: list[str]
    target_roles: list[str]
    skills: set[str]
    items: list[dict]  # 승인 항목: id, type, title, summary, embedding(list|None), months_ago
    pref_counts: dict[str, dict[str, int]] = field(default_factory=dict)
    outcomes: dict[str, dict[str, int]] = field(default_factory=dict)  # 분류별 accepted/rejected


def _norm(text: str) -> str:
    return re.sub(r"[^0-9a-z가-힣+#.]", "", text.lower())


def tokens(text: str) -> set[str]:
    return {t for t in (_norm(w) for w in re.split(r"[\s,/·()\[\]]+", text)) if len(t) >= 2}


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return 0.0 if na == 0 or nb == 0 else dot / (na * nb)


def profile_vector(ctx: UserContext, goal_vector: list[float] | None) -> list[float] | None:
    """승인 항목 임베딩의 시간 가중 평균 + 목표·관심 문장 임베딩, 정규화."""
    vecs = [
        (i["embedding"], 0.5 ** (i["months_ago"] / C.RECENCY_HALF_LIFE_MONTHS)) for i in ctx.items
    ]
    vecs = [(v, w) for v, w in vecs if v]
    if goal_vector:
        vecs.append((goal_vector, 1.0))
    if not vecs:
        return None
    dim = len(vecs[0][0])
    acc = [0.0] * dim
    total = sum(w for _, w in vecs)
    for v, w in vecs:
        for k in range(dim):
            acc[k] += v[k] * w / total
    n = math.sqrt(sum(x * x for x in acc)) or 1.0
    return [x / n for x in acc]


def keyword_sim(ctx: UserContext, opp: dict) -> float:
    mine: set[str] = set()
    for text in [*ctx.interests, *ctx.target_roles, *ctx.skills, *(i["title"] for i in ctx.items)]:
        mine |= tokens(text)
    theirs = tokens(" ".join([opp["title"], opp.get("summary") or "", *(opp.get("tags") or [])]))
    if not mine or not theirs:
        return 0.0
    overlap = len(mine & theirs)
    return min(1.0, overlap / math.sqrt(len(theirs) * min(len(mine), 30)) * 1.5)


def has_research(ctx: UserContext) -> bool:
    if any(i["type"] == "publication" for i in ctx.items):
        return True
    return any(
        i["type"] == "experience" and any(h in (i["title"] or "").lower() for h in C.RESEARCH_HINTS)
        for i in ctx.items
    )


def gap_score(ctx: UserContext, opp: dict) -> float:
    cat = opp["category"]
    if ctx.goal == "grad_school" and cat in RESEARCH_CATS and not has_research(ctx):
        return 1.0
    if ctx.goal == "employment" and cat in INTERNSHIP_CATS:
        if not any(i["type"] == "experience" for i in ctx.items):
            return 1.0
    role_words = set()
    for r in ctx.target_roles:
        role_words |= tokens(r)
    tags = set()
    for t in opp.get("tags") or []:
        tags |= tokens(t)
    skills = set()
    for sk in ctx.skills:
        skills |= tokens(sk)
    if role_words & tags and (tags - skills):
        missing = (role_words & tags) - skills
        if missing:
            return 1.0
    return 0.0


def pref_score(ctx: UserContext, category: str) -> float:
    c = ctx.pref_counts.get(category, {})
    pos = c.get("interested", 0) + c.get("applied", 0)
    neg = c.get("dismissed", 0)
    total = pos + neg
    value = max(-1.0, min(1.0, (pos - neg) / (total + C.PREF_PRIOR)))
    o = ctx.outcomes.get(category, {})
    if o.get("rejected", 0) >= C.REJECT_PENALTY_MIN_REJECTS and o.get("accepted", 0) == 0:
        value -= C.REJECT_PENALTY
    return value


def urgency_score(deadline: date | None, today: date) -> float:
    return 1.0 if deadline and (deadline - today).days <= C.URGENT_DAYS else 0.0


def score(
    ctx: UserContext, opp: dict, today: date, profile_vec: list[float] | None
) -> dict[str, Any]:
    if profile_vec and opp.get("embedding"):
        sim = max(0.0, cosine(profile_vec, opp["embedding"]))
    else:
        sim = keyword_sim(ctx, opp)
    parts = {
        "sim": round(sim, 4),
        "gap": gap_score(ctx, opp),
        "pref": round(pref_score(ctx, opp["category"]), 4),
        "urgency": urgency_score(opp.get("apply_deadline"), today),
    }
    total = (
        C.W_SIM * parts["sim"]
        + C.W_GAP * parts["gap"]
        + C.W_PREF * parts["pref"]
        + C.W_URGENCY * parts["urgency"]
    )
    return {"score": round(total, 4), "breakdown": parts}


def diversify(ranked: list[dict]) -> list[dict]:
    """상위 10개 안에서 같은 분류는 최대 3개. 밀린 공고는 그 뒤로 보낸다."""
    top: list[dict] = []
    rest: list[dict] = []
    per_cat: dict[str, int] = {}
    for r in ranked:
        cat = r["category"]
        if len(top) < C.DIVERSITY_TOP and per_cat.get(cat, 0) < C.DIVERSITY_MAX_PER_CATEGORY:
            top.append(r)
            per_cat[cat] = per_cat.get(cat, 0) + 1
        else:
            rest.append(r)
    return top + rest


def eligible(opp: dict, grade: int | None, major: str | None) -> bool:
    elig = opp.get("eligibility") or {}
    grades = elig.get("grades") or []
    if grades and grade is not None and grade not in grades:
        return False
    majors = elig.get("majors") or []
    if majors and major:
        m = _norm(major)
        if not any(_norm(x) in m or m in _norm(x) for x in majors):
            return False
    return True


def related_items(ctx: UserContext, opp: dict, limit: int = 5) -> list[dict]:
    """이유 작성에 넘길, 공고와 가까운 항목 5개."""
    if opp.get("embedding") and any(i["embedding"] for i in ctx.items):
        scored = [
            (cosine(i["embedding"], opp["embedding"]) if i["embedding"] else 0, i)
            for i in ctx.items
        ]
    else:
        theirs = tokens(
            " ".join([opp["title"], opp.get("summary") or "", *(opp.get("tags") or [])])
        )
        scored = [(len(tokens(f"{i['title']} {i['summary']}") & theirs), i) for i in ctx.items]
    scored.sort(key=lambda x: x[0], reverse=True)
    return [i for _, i in scored[:limit]]


def as_uuid_list(ids: list[Any], allowed: set[UUID]) -> list[UUID]:
    out = []
    for x in ids:
        try:
            u = x if isinstance(x, UUID) else UUID(str(x))
        except ValueError:
            continue
        if u in allowed and u not in out:
            out.append(u)
    return out
