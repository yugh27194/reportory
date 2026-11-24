"""성장 나무, 스펙 레이더, 일기 책장(달력) 데이터."""

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.db import UserDB, as_json, get_user_db
from app.routers.me import ensure_profile
from app.services.growth import PRESETS, RADAR_AXES, resolve_target, stage_for

router = APIRouter(tags=["growth"])


async def _counts(db: UserDB) -> dict[str, int]:
    rows = await db.all(
        """select type, count(*) as n from items
           where user_id = :user_id and status = 'approved' group by type"""
    )
    return {r["type"]: r["n"] for r in rows}


@router.get("/me/growth")
async def growth(db: UserDB = Depends(get_user_db)):
    profile = await ensure_profile(db)
    counts = await _counts(db)
    days = await db.scalar(
        "select count(distinct entry_date) from entries where user_id = :user_id"
    )
    stored = await db.scalar("select spec_target from profiles where id = :user_id")
    items = sum(counts.values())
    return {
        "stage": stage_for(items * 2 + (days or 0)),
        "items_total": items,
        "entry_days": days or 0,
        "counts": counts,
        "radar": {
            "axes": RADAR_AXES,
            "values": {a: counts.get(a, 0) for a in RADAR_AXES},
            "target": resolve_target(stored, profile["goal"]),
        },
        "presets": {k: v for k, v in PRESETS.items()},
    }


class SpecTargetIn(BaseModel):
    preset: Literal["dev_job", "biz_job", "public_job", "grad_school", "custom"]
    values: dict[str, int] | None = None


@router.put("/me/spec-target")
async def put_spec_target(body: SpecTargetIn, db: UserDB = Depends(get_user_db)):
    await ensure_profile(db)
    values = {k: max(0, min(20, int(v))) for k, v in (body.values or {}).items() if k in RADAR_AXES}
    if body.preset != "custom":
        values = {}
    await db.execute(
        "update profiles set spec_target = cast(:t as jsonb) where id = :user_id",
        t=as_json({"preset": body.preset, "values": values}),
    )
    profile = await ensure_profile(db)
    stored = await db.scalar("select spec_target from profiles where id = :user_id")
    return resolve_target(stored, profile["goal"])


@router.get("/journal/calendar")
async def calendar(
    db: UserDB = Depends(get_user_db),
    year: int | None = Query(default=None, ge=1990, le=2100),
):
    """책장: 일기를 쓴 해 목록과 그 해의 날짜별 편수. 본문은 보내지 않는다."""
    year = year or date.today().year
    years = await db.all(
        """select distinct cast(extract(year from entry_date) as int) as y from entries
           where user_id = :user_id order by y"""
    )
    days = await db.all(
        """select entry_date, count(*) as n, sum(char_length(body)) as chars from entries
           where user_id = :user_id and extract(year from entry_date) = :y
           group by entry_date order by entry_date""",
        y=year,
    )
    approved = await db.all(
        """select e.entry_date, count(distinct s.item_id) as n
           from item_sources s join entries e on e.id = s.entry_id
           join items i on i.id = s.item_id and i.status = 'approved'
           where s.user_id = :user_id and extract(year from e.entry_date) = :y
           group by e.entry_date""",
        y=year,
    )
    found = {r["entry_date"].isoformat(): r["n"] for r in approved}
    year_list = sorted({r["y"] for r in years} | {date.today().year})
    return {
        "year": year,
        "years": year_list,
        "days": {
            r["entry_date"].isoformat(): {
                "entries": r["n"],
                "chars": r["chars"] or 0,
                "items": found.get(r["entry_date"].isoformat(), 0),
            }
            for r in days
        },
    }
