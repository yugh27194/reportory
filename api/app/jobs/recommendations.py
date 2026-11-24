"""사용자별 추천 계산(score_recommendations, 인계서 10.7절)."""

import json
import logging
from datetime import date
from typing import Any
from uuid import UUID

from app.config import get_settings
from app.db import UserDB, as_json
from app.jobs.opportunities import today_kst
from app.llm.calls import call_logger
from app.llm.client import LLMError, get_llm
from app.llm.schemas import RecoReason
from app.llm.validators import numbers_supported
from app.services import recommend as R
from app.services.similarity import safe_embed

log = logging.getLogger("reportory.recommend")

GOAL_LABELS = {"grad_school": "대학원 진학", "employment": "취업", "undecided": "진로 탐색"}
CATEGORY_LABELS = {
    "contest": "공모전",
    "hackathon": "해커톤",
    "external_activity": "대외활동",
    "internship": "인턴십",
    "research_internship": "연구 인턴",
    "education": "교육",
    "scholarship": "장학금",
    "other": "활동",
}


def _vec(text: str | None) -> list[float] | None:
    return json.loads(text) if text else None


async def load_context(db: UserDB, today: date) -> R.UserContext:
    p = await db.one(
        """select goal, grade, major, interests, target_roles from profiles where id = :user_id"""
    )
    items = await db.all(
        """select id, type, title, summary, cast(embedding as text) as emb,
                  coalesce(end_date, start_date, approved_at::date, created_at::date) as ref_date
           from items where user_id = :user_id and status = 'approved'"""
    )
    skills = await db.all(
        """select distinct s.name from item_skills x join skills s on s.id = x.skill_id
           join items i on i.id = x.item_id and i.status = 'approved'
           where x.user_id = :user_id"""
    )
    prefs = await db.all(
        """select o.category, r.feedback, count(*) as n from recommendations r
           join opportunities o on o.id = r.opportunity_id
           where r.user_id = :user_id and r.feedback is not null group by 1, 2"""
    )
    outcomes = await db.all(
        """select category, status, count(*) as n from applications
           where user_id = :user_id and status in ('accepted', 'active', 'completed', 'rejected')
           group by 1, 2"""
    )
    ctx = R.UserContext(
        goal=(p or {}).get("goal") or "undecided",
        grade=(p or {}).get("grade"),
        major=(p or {}).get("major"),
        interests=list((p or {}).get("interests") or []),
        target_roles=list((p or {}).get("target_roles") or []),
        skills={r["name"] for r in skills},
        items=[
            {
                "id": i["id"],
                "type": i["type"],
                "title": i["title"],
                "summary": i["summary"] or "",
                "embedding": _vec(i["emb"]),
                "months_ago": max(0.0, (today - i["ref_date"]).days / 30.4)
                if i["ref_date"]
                else 0.0,
            }
            for i in items
        ],
    )
    for r in prefs:
        ctx.pref_counts.setdefault(r["category"], {})[r["feedback"]] = r["n"]
    for r in outcomes:
        key = "rejected" if r["status"] == "rejected" else "accepted"
        bucket = ctx.outcomes.setdefault(r["category"], {})
        bucket[key] = bucket.get(key, 0) + r["n"]
    return ctx


async def candidates(db: UserDB, only: UUID | None) -> list[dict]:
    """활성·마감 전(내일 이후)·본인에게 보이는 공고 중 지원했거나 숨긴 것은 뺀다.

    본인이 URL로 넣은 공고는 마감일을 몰라도 넣는다(지난 공고만 뺀다).
    """
    rows = await db.all(
        """select o.id, o.title, o.organizer, o.category, o.summary, o.eligibility, o.tags,
                  o.apply_deadline, cast(o.embedding as text) as emb, o.created_by
           from opportunities o
           where o.is_active
             and (o.created_by is null or o.created_by = :user_id)
             and (o.apply_deadline >= current_date + 1
                  or (o.created_by = :user_id and o.apply_deadline is null))
             and (cast(:only as uuid) is null or o.id = cast(:only as uuid))
             and not exists (select 1 from applications a
                             where a.user_id = :user_id and a.opportunity_id = o.id)
             and not exists (select 1 from recommendations r
                             where r.user_id = :user_id and r.opportunity_id = o.id
                               and r.feedback = 'dismissed')""",
        only=str(only) if only else None,
    )
    for r in rows:
        r["embedding"] = _vec(r.pop("emb"))
        r["category"] = str(r["category"])
    return rows


def fallback_reason(
    ctx: R.UserContext, opp: dict, related: list[dict], gap: bool
) -> tuple[str, list]:
    cat = CATEGORY_LABELS.get(opp["category"], "활동")
    goal = GOAL_LABELS.get(ctx.goal, "진로 탐색")
    if gap:
        first = f"{goal} 목표에 아직 없는 경험을 채울 수 있는 {cat}이다."
    else:
        first = f"{goal} 목표와 관심 분야에 맞는 {cat} 공고다."
    if related:
        return f"{first} '{related[0]['title']}' 경험과 이어진다.", [related[0]["id"]]
    return first, []


async def make_reason(
    db: UserDB, ctx: R.UserContext, opp: dict, gap: bool
) -> tuple[str, list[UUID]]:
    related = R.related_items(ctx, opp)
    variables: dict[str, Any] = {
        "GOAL": GOAL_LABELS.get(ctx.goal, ctx.goal),
        "OPPORTUNITY": {
            "title": opp["title"],
            "organizer": opp.get("organizer"),
            "category": opp["category"],
            "summary": opp.get("summary"),
            "tags": opp.get("tags") or [],
            "apply_deadline": opp["apply_deadline"].isoformat()
            if opp.get("apply_deadline")
            else None,
        },
        "ITEMS": [
            {"id": str(i["id"]), "type": i["type"], "title": i["title"], "summary": i["summary"]}
            for i in related
        ],
        "GAP": gap,
    }
    try:
        out = await get_llm().complete_json(
            "reco_reason", "reco_reason", variables, RecoReason, "light", log_call=call_logger(db)
        )
    except LLMError as exc:
        log.warning("reason fallback: %s", type(exc).__name__)
        return fallback_reason(ctx, opp, related, gap)
    # id(uuid)의 숫자가 섞이지 않게 사람이 읽는 글만 근거로 쓴다.
    o = variables["OPPORTUNITY"]
    source = " ".join(
        str(x)
        for x in [
            o["title"],
            o["organizer"],
            o["summary"],
            " ".join(o["tags"]),
            o["apply_deadline"],
        ]
        + [f"{i['title']} {i['summary']}" for i in variables["ITEMS"]]
        if x
    )
    reason = out.reason.strip()
    if not reason or not numbers_supported(reason, source):
        return fallback_reason(ctx, opp, related, gap)
    ids = R.as_uuid_list(out.reason_item_ids, {i["id"] for i in related})[:3]
    return reason[:300], ids


async def run(db: UserDB, payload: dict) -> dict:
    s = get_settings()
    today = today_kst()
    only = UUID(payload["only_opportunity_id"]) if payload.get("only_opportunity_id") else None
    ctx = await load_context(db, today)
    goal_text = " ".join([GOAL_LABELS.get(ctx.goal, ""), *ctx.interests, *ctx.target_roles]).strip()
    goal_vec = None
    if goal_text and any(i["embedding"] for i in ctx.items):
        vecs = await safe_embed([goal_text])
        goal_vec = vecs[0] if vecs else None
    pvec = R.profile_vector(ctx, goal_vec)
    if pvec and not only:
        await db.execute(
            "update profiles set profile_embedding = cast(:v as vector) where id = :user_id",
            v=str(pvec),
        )
    scored = []
    for opp in await candidates(db, only):
        if not R.eligible(opp, ctx.grade, ctx.major):
            continue
        result = R.score(ctx, opp, today, pvec)
        scored.append({**opp, **result})
    scored.sort(key=lambda r: r["score"], reverse=True)
    ranked = R.diversify(scored)[: s.reco_top_n]

    existing = {
        r["opportunity_id"]: r
        for r in await db.all(
            "select opportunity_id, reason, reason_item_ids from recommendations where user_id = :user_id"
        )
    }
    for idx, r in enumerate(ranked):
        prev = existing.get(r["id"])
        approved_ids = {i["id"] for i in ctx.items}
        if prev and prev["reason"] and set(prev["reason_item_ids"] or []) <= approved_ids:
            reason, reason_ids = prev["reason"], list(prev["reason_item_ids"] or [])
        else:
            reason, reason_ids = None, []
        if reason is None and idx < s.reco_reason_top_n:
            reason, reason_ids = await make_reason(db, ctx, r, r["breakdown"]["gap"] > 0)
        await db.execute(
            """insert into recommendations (user_id, opportunity_id, score, score_breakdown, reason,
                 reason_item_ids, generated_at)
               values (:user_id, :oid, :score, cast(:bd as jsonb), :reason,
                 cast(:rids as uuid[]), now())
               on conflict (user_id, opportunity_id) do update set
                 score = excluded.score, score_breakdown = excluded.score_breakdown,
                 reason = excluded.reason, reason_item_ids = excluded.reason_item_ids,
                 generated_at = now()""",
            oid=r["id"],
            score=r["score"],
            bd=as_json(r["breakdown"]),
            reason=reason,
            rids=[str(x) for x in reason_ids],
        )
    removed = 0
    if not only:
        removed = await db.execute(
            """delete from recommendations
               where user_id = :user_id and feedback is null
                 and not (opportunity_id = any(cast(:keep as uuid[])))""",
            keep=[str(r["id"]) for r in ranked],
        )
    return {"recommended": len(ranked), "removed": removed}
