"""항목 임베딩 계산(인계서 13.1절 embed_item)."""

from uuid import UUID

from app.db import UserDB
from app.embeddings import embed
from app.services.skills import skills_of


def item_text(item: dict, skills: list[str]) -> str:
    parts = [
        item["title"],
        item["organization"] or "",
        item["role"] or "",
        item["summary"],
        ", ".join(skills),
    ]
    return "\n".join(p for p in parts if p)


async def run(db: UserDB, payload: dict) -> dict:
    item_id = UUID(payload["item_id"])
    item = await db.one(
        """select id, title, organization, role, summary, status from items
           where id = :id and user_id = :user_id""",
        id=item_id,
    )
    if item is None or item["status"] != "approved":
        return {"skipped": "not_approved"}
    vectors = await embed([item_text(item, await skills_of(db, item_id))])
    if vectors is None:
        return {"skipped": "no_embedding_provider"}
    await db.execute(
        "update items set embedding = cast(:v as vector) where id = :id and user_id = :user_id",
        id=item_id,
        v=str(vectors[0]),
    )
    return {"embedded": True}
