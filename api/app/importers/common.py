"""가져오기 공통: 후보를 제안으로 저장하고, 같은 항목은 하나로 합친다(인계서 10.9절)."""

from dataclasses import dataclass, field
from uuid import UUID

from app.db import UserDB, as_json
from app.llm.schemas import ItemCandidate
from app.services.similarity import find_duplicates
from app.services.skills import link_skills, normalize_skill


@dataclass
class ImportResult:
    items_proposed: int = 0
    merged: int = 0
    dropped: int = 0
    skipped: list[str] = field(default_factory=list)
    notes: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "items_proposed": self.items_proposed,
            "merged": self.merged,
            "dropped": self.dropped,
            "skipped": self.skipped,
            **self.notes,
        }


async def reset_import(db: UserDB, import_id: UUID) -> None:
    """멱등: 같은 가져오기에서 나온 대기 제안과 제안 상태 항목을 정리한다."""
    await db.execute(
        """update items set status = 'rejected' where user_id = :user_id and status = 'proposed'
             and id in (select item_id from proposals where user_id = :user_id
                        and import_id = :id and status = 'pending' and kind = 'create_item')""",
        id=import_id,
    )
    await db.execute(
        """delete from proposals where user_id = :user_id and import_id = :id
             and status = 'pending'""",
        id=import_id,
    )
    await db.execute(
        """delete from item_sources where user_id = :user_id and import_id = :id
             and item_id in (select id from items where user_id = :user_id
                             and status in ('proposed', 'rejected'))""",
        id=import_id,
    )


async def save_candidates(
    db: UserDB, import_id: UUID, cands: list[ItemCandidate], result: ImportResult
) -> None:
    """create 후보를 저장한다. 같은 실행 안의 중복은 하나로 합치고, 이미 제안 상태인 같은 항목이 있으면
    새 제안 대신 그 항목에 근거만 더한다. 승인된 같은 항목이 있으면 중복 의심으로 표시한다."""
    unique: list[ItemCandidate] = []
    seen: dict[tuple[str, str], int] = {}
    for c in cands:
        if c.action != "create":
            result.dropped += 1
            continue
        key = (c.type, normalize_skill(c.title))
        if key in seen:
            result.merged += 1
            continue
        seen[key] = len(unique)
        unique.append(c)

    dups = await find_duplicates(db, unique)
    for cand, dup in zip(unique, dups, strict=True):
        if dup is not None:
            status = await db.scalar(
                "select status from items where id = :id and user_id = :user_id", id=dup
            )
            if status == "proposed":
                await db.execute(
                    """insert into item_sources (item_id, user_id, import_id, quote)
                       values (:item_id, :user_id, :import_id, :quote)""",
                    item_id=dup,
                    import_id=import_id,
                    quote=cand.quote,
                )
                await link_skills(db, dup, cand.skills)
                result.merged += 1
                continue
        item_id = await db.scalar(
            """insert into items (user_id, type, status, title, organization, role, start_date,
                 end_date, is_ongoing, summary, details, metrics)
               values (:user_id, cast(:type as item_type), 'proposed', :title, :org, :role,
                 :start, :end, :ongoing, :summary, cast(:details as jsonb),
                 cast(:metrics as jsonb))
               returning id""",
            type=cand.type,
            title=cand.title[:200],
            org=cand.organization,
            role=cand.role,
            start=cand.start_date,
            end=cand.end_date,
            ongoing=bool(cand.is_ongoing),
            summary=cand.summary_append,
            details=as_json(cand.details),
            metrics=as_json([m.model_dump() for m in cand.metrics]),
        )
        await link_skills(db, item_id, cand.skills)
        await db.execute(
            """insert into item_sources (item_id, user_id, import_id, quote)
               values (:item_id, :user_id, :import_id, :quote)""",
            item_id=item_id,
            import_id=import_id,
            quote=cand.quote,
        )
        await db.execute(
            """insert into proposals (user_id, kind, payload, item_id, import_id, confidence,
                 quote, possible_duplicate_of)
               values (:user_id, 'create_item', cast(:payload as jsonb), :item_id, :import_id,
                 :confidence, :quote, :dup)""",
            payload=as_json({"item_id": str(item_id)}),
            item_id=item_id,
            import_id=import_id,
            confidence=cand.confidence,
            quote=cand.quote,
            dup=dup,
        )
        result.items_proposed += 1
