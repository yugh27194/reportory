"""포트폴리오 항목(인계서 9.2절 /items, 11.2절)."""

from datetime import date
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.db import UserDB, as_json, get_user_db
from app.llm.schemas import ItemType, Metric
from app.services.items import ITEM_COLUMNS, filter_details, get_item, item_detail, merge_items
from app.services.jobs import enqueue
from app.services.proposals import _check_dates
from app.services.skills import link_skills, normalize_skill

router = APIRouter(tags=["items"])


class LinkIn(BaseModel):
    label: str = Field(min_length=1, max_length=50)
    url: str = Field(pattern=r"^https?://", max_length=500)


class ItemIn(BaseModel):
    type: ItemType
    title: str = Field(min_length=1, max_length=200)
    title_en: str | None = Field(default=None, max_length=200)
    organization: str | None = None
    role: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    is_ongoing: bool = False
    summary: str = ""
    details: dict[str, Any] = {}
    metrics: list[Metric] = []
    links: list[LinkIn] = []
    skills: list[str] = []
    visibility: Literal["private", "public"] = "private"


class ItemPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    title_en: str | None = None
    organization: str | None = None
    role: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    is_ongoing: bool | None = None
    summary: str | None = None
    details: dict[str, Any] | None = None
    metrics: list[Metric] | None = None
    links: list[LinkIn] | None = None
    skills: list[str] | None = None
    visibility: Literal["private", "public"] | None = None


@router.get("/items")
async def list_items(
    type: ItemType | None = None,
    status: Literal["approved", "proposed", "archived", "rejected"] = "approved",
    skill: str | None = None,
    db: UserDB = Depends(get_user_db),
):
    rows = await db.all(
        f"""select {", ".join("i." + c.strip() for c in ITEM_COLUMNS.split(","))},
                   coalesce((select jsonb_agg(s.name order by s.name) from item_skills isk
                     join skills s on s.id = isk.skill_id
                     where isk.item_id = i.id and isk.user_id = i.user_id), '[]'::jsonb) as skills,
                   (select count(*) from item_sources src
                     where src.item_id = i.id and src.user_id = i.user_id) as source_count
            from items i
            where i.user_id = :user_id and i.status = cast(:status as item_status)
              and (cast(:type as text) is null or i.type = cast(:type as item_type))
              and (cast(:skill as text) is null or exists (
                select 1 from item_skills isk join skills s on s.id = isk.skill_id
                where isk.item_id = i.id and s.normalized = :skill))
            order by coalesce(i.end_date, i.start_date, i.created_at::date) desc, i.created_at desc""",
        status=status,
        type=type,
        skill=normalize_skill(skill) if skill else None,
    )
    return {"items": rows}


@router.post("/items", status_code=201)
async def create_item(body: ItemIn, db: UserDB = Depends(get_user_db)):
    """수동 항목은 바로 approved가 되고, 근거로 imports(source='manual') 행을 남긴다."""
    _check_dates(body.model_dump())
    item_id = await db.scalar(
        """insert into items (user_id, type, status, title, title_en, organization, role,
             start_date, end_date, is_ongoing, summary, details, metrics, links, visibility,
             approved_at)
           values (:user_id, cast(:type as item_type), 'approved', :title, :title_en,
             :organization, :role, :start_date, :end_date, :is_ongoing, :summary,
             cast(:details as jsonb), cast(:metrics as jsonb), cast(:links as jsonb),
             cast(:visibility as visibility), now())
           returning id""",
        type=body.type,
        title=body.title,
        title_en=body.title_en,
        organization=body.organization,
        role=body.role,
        start_date=body.start_date,
        end_date=body.end_date,
        is_ongoing=body.is_ongoing,
        summary=body.summary,
        details=as_json(filter_details(body.type, body.details)),
        metrics=as_json([m.model_dump() for m in body.metrics]),
        links=as_json([link.model_dump() for link in body.links]),
        visibility=body.visibility,
    )
    import_id = await db.scalar(
        """insert into imports (user_id, source, status, summary, finished_at)
           values (:user_id, 'manual', 'succeeded', cast(:s as jsonb), now()) returning id""",
        s=as_json({"item_id": str(item_id)}),
    )
    await db.execute(
        """insert into item_sources (item_id, user_id, import_id)
           values (:item_id, :user_id, :import_id)""",
        item_id=item_id,
        import_id=import_id,
    )
    await link_skills(db, item_id, body.skills)
    await enqueue(db, "embed_item", {"item_id": str(item_id)})
    return await item_detail(db, item_id)


@router.get("/items/{item_id}")
async def get_item_detail(item_id: UUID, db: UserDB = Depends(get_user_db)):
    return await item_detail(db, item_id)


@router.patch("/items/{item_id}")
async def patch_item(item_id: UUID, body: ItemPatch, db: UserDB = Depends(get_user_db)):
    item = await get_item(db, item_id, statuses=("approved", "proposed"))
    values = body.model_dump(exclude_unset=True)
    skills = values.pop("skills", None)
    _check_dates({**item, **values})
    sets, params = [], {}
    for key, value in values.items():
        if key in ("details", "metrics", "links"):
            if key == "details":
                value = filter_details(item["type"], value or {})
            sets.append(f"{key} = cast(:{key} as jsonb)")
            params[key] = as_json(value or ([] if key != "details" else {}))
        elif key == "visibility":
            sets.append("visibility = cast(:visibility as visibility)")
            params[key] = value
        elif key in ("title", "summary", "is_ongoing") and value is None:
            continue
        else:
            sets.append(f"{key} = :{key}")
            params[key] = value
    if sets:
        await db.execute(
            f"update items set {', '.join(sets)} where id = :id and user_id = :user_id",
            id=item_id,
            **params,
        )
    if skills is not None:
        await db.execute(
            "delete from item_skills where item_id = :id and user_id = :user_id", id=item_id
        )
        await link_skills(db, item_id, skills)
    if item["status"] == "approved":
        await enqueue(db, "embed_item", {"item_id": str(item_id)})
    return await item_detail(db, item_id)


@router.delete("/items/{item_id}")
async def archive_item(item_id: UUID, db: UserDB = Depends(get_user_db)):
    await get_item(db, item_id, statuses=("approved", "proposed"))
    await db.execute(
        "update items set status = 'archived' where id = :id and user_id = :user_id", id=item_id
    )
    await db.execute(
        """update proposals set status = 'rejected', resolved_at = now()
           where user_id = :user_id and status = 'pending' and item_id = :id""",
        id=item_id,
    )
    return {"id": item_id, "status": "archived"}


class MergeIn(BaseModel):
    keep_item_id: UUID
    merge_item_ids: list[UUID] = Field(min_length=1, max_length=20)


@router.post("/items/merge")
async def merge(body: MergeIn, db: UserDB = Depends(get_user_db)):
    await merge_items(db, body.keep_item_id, body.merge_item_ids)
    return await item_detail(db, body.keep_item_id)
