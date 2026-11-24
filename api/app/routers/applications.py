"""지원 관리(인계서 9.2절 /applications, 11.3절)."""

from datetime import date
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.db import UserDB, get_user_db
from app.errors import validation_error
from app.services.applications import (
    APP_COLUMNS,
    create_application,
    get_application,
    transition,
)

router = APIRouter(tags=["applications"])

Category = Literal[
    "contest",
    "hackathon",
    "external_activity",
    "internship",
    "research_internship",
    "education",
    "scholarship",
    "other",
]
Status = Literal[
    "interested",
    "applied",
    "awaiting_result",
    "accepted",
    "rejected",
    "withdrawn",
    "active",
    "completed",
]


@router.get("/applications")
async def list_applications(db: UserDB = Depends(get_user_db), status: Status | None = Query(None)):
    return {
        "applications": await db.all(
            f"""select {APP_COLUMNS} from applications
                where user_id = :user_id
                  and (cast(:st as application_status) is null
                       or status = cast(:st as application_status))
                order by coalesce(apply_deadline, '9999-12-31'), created_at desc""",
            st=status,
        )
    }


class ApplicationIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    organizer: str | None = Field(default=None, max_length=200)
    category: Category = "other"
    apply_deadline: date | None = None
    result_announce_on: date | None = None
    activity_start: date | None = None
    activity_end: date | None = None


@router.post("/applications", status_code=201)
async def create(body: ApplicationIn, db: UserDB = Depends(get_user_db)):
    return await create_application(db, body.model_dump())


@router.get("/applications/{app_id}")
async def detail(app_id: UUID, db: UserDB = Depends(get_user_db)):
    app = await get_application(db, app_id)
    app["events"] = await db.all(
        """select from_status, to_status, source, entry_id, note, created_at
           from application_events where user_id = :user_id and application_id = :id
           order by created_at""",
        id=app_id,
    )
    app["opportunity"] = (
        await db.one(
            """select id, source_url, summary, benefits, tags from opportunities
               where id = :oid and (created_by is null or created_by = :user_id)""",
            oid=app["opportunity_id"],
        )
        if app["opportunity_id"]
        else None
    )
    return app


class ApplicationPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    organizer: str | None = Field(default=None, max_length=200)
    apply_deadline: date | None = None
    result_announce_on: date | None = None
    activity_start: date | None = None
    activity_end: date | None = None
    result_note: str | None = Field(default=None, max_length=500)
    submitted_version_id: UUID | None = None


@router.patch("/applications/{app_id}")
async def patch(app_id: UUID, body: ApplicationPatch, db: UserDB = Depends(get_user_db)):
    await get_application(db, app_id)
    values = body.model_dump(exclude_unset=True)
    if "submitted_version_id" in values and values["submitted_version_id"]:
        ok = await db.scalar(
            """select 1 from document_versions v join documents d on d.id = v.document_id
               where v.id = :vid and d.user_id = :user_id""",
            vid=values["submitted_version_id"],
        )
        if not ok:
            raise validation_error("내 문서 버전만 고를 수 있다.")
    if values:
        sets = ", ".join(f"{k} = :{k}" for k in values)
        await db.execute(
            f"update applications set {sets}, updated_at = now() where id = :id and user_id = :user_id",
            id=app_id,
            **values,
        )
    return await get_application(db, app_id)


class TransitionIn(BaseModel):
    to_status: Status
    result_date: date | None = None
    note: str | None = Field(default=None, max_length=500)


@router.post("/applications/{app_id}/transition")
async def do_transition(app_id: UUID, body: TransitionIn, db: UserDB = Depends(get_user_db)):
    return await transition(
        db, app_id, body.to_status, source="manual", note=body.note, result_date=body.result_date
    )


class ReflectionIn(BaseModel):
    reflection: str = Field(min_length=1, max_length=1000)


@router.post("/applications/{app_id}/reflection")
async def reflection(app_id: UUID, body: ReflectionIn, db: UserDB = Depends(get_user_db)):
    await get_application(db, app_id)
    await db.execute(
        """update applications set reflection = :r, updated_at = now()
           where id = :id and user_id = :user_id""",
        r=body.reflection,
        id=app_id,
    )
    return await get_application(db, app_id)
