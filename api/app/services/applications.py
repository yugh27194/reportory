"""지원 항목 상태 전이(인계서 8.3절). 상태 전이는 이 모듈의 `transition` 한 함수에서만 처리한다."""

from datetime import date
from typing import Any
from uuid import UUID

from app.db import UserDB
from app.errors import invalid_transition, not_found

ALLOWED_TRANSITIONS: dict[str | None, set[str]] = {
    None: {"interested"},
    "interested": {"applied", "withdrawn"},
    "applied": {"awaiting_result", "accepted", "rejected", "withdrawn"},
    "awaiting_result": {"accepted", "rejected", "withdrawn"},
    "accepted": {"active"},
    "active": {"completed"},
    "rejected": set(),
    "withdrawn": set(),
    "completed": set(),
}

OPEN_STATUSES = ("applied", "awaiting_result", "accepted", "active")

# 합격하면 만드는 항목의 유형(공고 분류 → 항목 유형)
CATEGORY_TO_ITEM_TYPE = {
    "hackathon": "project",
    "internship": "experience",
    "research_internship": "experience",
    "scholarship": "award",
}

APP_COLUMNS = """id, opportunity_id, title, organizer, category, status, apply_deadline, applied_at,
  result_announce_on, result_at, activity_start, activity_end, result_note, reflection, item_id,
  submitted_version_id, created_at, updated_at"""


def is_allowed(from_status: str | None, to_status: str) -> bool:
    return to_status in ALLOWED_TRANSITIONS.get(from_status, set())


async def get_application(db: UserDB, app_id: UUID) -> dict:
    row = await db.one(
        f"select {APP_COLUMNS} from applications where id = :id and user_id = :user_id", id=app_id
    )
    if row is None:
        raise not_found("지원 항목을 찾을 수 없다.")
    return row


async def create_application(db: UserDB, values: dict[str, Any], *, source: str = "manual") -> dict:
    """(없음) → interested. 공고에서 만들면 공고 정보(마감·발표·활동 기간)를 복사한다."""
    app_id = await db.scalar(
        """insert into applications (user_id, opportunity_id, title, organizer, category,
             status, apply_deadline, result_announce_on, activity_start, activity_end)
           values (:user_id, :opp, :title, :organizer, cast(:category as opportunity_category),
             'interested', :deadline, :announce, :astart, :aend)
           returning id""",
        opp=values.get("opportunity_id"),
        title=values["title"],
        organizer=values.get("organizer"),
        category=values.get("category") or "other",
        deadline=values.get("apply_deadline"),
        announce=values.get("result_announce_on"),
        astart=values.get("activity_start"),
        aend=values.get("activity_end"),
    )
    await _event(db, app_id, None, "interested", source)
    return await get_application(db, app_id)


async def _event(db, app_id, from_status, to_status, source, entry_id=None, note=None) -> None:
    await db.execute(
        """insert into application_events (application_id, user_id, from_status, to_status, source,
             entry_id, note)
           values (:aid, :user_id, cast(:f as application_status), cast(:t as application_status),
             cast(:src as event_source), :entry_id, :note)""",
        aid=app_id,
        f=from_status,
        t=to_status,
        src=source,
        entry_id=entry_id,
        note=note,
    )


async def transition(
    db: UserDB,
    app_id: UUID,
    to_status: str,
    *,
    source: str = "manual",
    entry_id: UUID | None = None,
    note: str | None = None,
    result_date: date | None = None,
    today: date | None = None,
) -> dict:
    """허용된 전이만 한다(아니면 409). 부수 효과(항목 생성·활동 시작·완료)도 여기서 처리한다."""
    today = today or date.today()
    app = await get_application(db, app_id)
    current = app["status"]
    if not is_allowed(current, to_status):
        raise invalid_transition(f"'{current}'에서 '{to_status}'(으)로 바꿀 수 없다.")
    sets = ["status = cast(:to as application_status)", "updated_at = now()"]
    params: dict[str, Any] = {"to": to_status, "id": app_id}
    if to_status == "applied":
        sets.append("applied_at = coalesce(applied_at, :d)")
        params["d"] = result_date or today
    if to_status in ("accepted", "rejected"):
        sets.append("result_at = :d")
        params["d"] = result_date or today
    if note and to_status in ("accepted", "rejected", "withdrawn"):
        sets.append("result_note = :note")
        params["note"] = note[:500]
    await db.execute(
        f"update applications set {', '.join(sets)} where id = :id and user_id = :user_id", **params
    )
    await _event(db, app_id, current, to_status, source, entry_id, note)

    if to_status == "accepted":
        item_id = app["item_id"] or await _create_item(db, app)
        await db.execute(
            "update applications set item_id = :item where id = :id and user_id = :user_id",
            item=item_id,
            id=app_id,
        )
        start = app["activity_start"]
        if start is None or start <= today:
            return await transition(db, app_id, "active", source="system", today=today)
    if to_status == "completed" and app["item_id"]:
        await db.execute(
            """update items set is_ongoing = false,
                 end_date = coalesce(end_date, :d) where id = :item and user_id = :user_id""",
            item=app["item_id"],
            d=result_date or app["activity_end"] or today,
        )
    return await get_application(db, app_id)


async def _create_item(db: UserDB, app: dict) -> UUID:
    """합격하면 승인된 진행 중 항목을 하나 만든다. 유형은 공고 분류에서 정한다."""
    item_type = CATEGORY_TO_ITEM_TYPE.get(str(app["category"]), "activity")
    item_id = await db.scalar(
        """insert into items (user_id, type, status, title, organization, start_date, is_ongoing,
             summary, approved_at)
           values (:user_id, cast(:type as item_type), 'approved', :title, :org, :start, true, '',
             now())
           returning id""",
        type=item_type,
        title=app["title"],
        org=app["organizer"],
        start=app["activity_start"],
    )
    from app.services.jobs import enqueue

    await enqueue(db, "embed_item", {"item_id": str(item_id)})
    return item_id


async def auto_transitions(db: UserDB, today: date) -> int:
    """마감이 지난 지원 → awaiting_result, 활동 시작일이 된 합격 → active (system)."""
    n = 0
    for row in await db.all(
        """select id from applications where user_id = :user_id and status = 'applied'
             and apply_deadline is not null and apply_deadline < :today""",
        today=today,
    ):
        await transition(db, row["id"], "awaiting_result", source="system", today=today)
        n += 1
    for row in await db.all(
        """select id from applications where user_id = :user_id and status = 'accepted'
             and (activity_start is null or activity_start <= :today)""",
        today=today,
    ):
        await transition(db, row["id"], "active", source="system", today=today)
        n += 1
    return n
