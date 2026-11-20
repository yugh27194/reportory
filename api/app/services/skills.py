"""기술 이름 정규화와 항목 연결(인계서 11.2절)."""

import re
import unicodedata
from uuid import UUID

from app.db import UserDB

# "+"와 "#"은 남긴다. 지우면 C, C++, C#이 모두 "c"가 된다(docs/decisions.md).
_STRIP = re.compile(r"[^\w+#]|_", re.UNICODE)


def normalize_skill(name: str) -> str:
    """소문자로 바꾸고 공백·구두점을 지운다. "PyTorch", "py torch", "Py-Torch"는 같다."""
    text = unicodedata.normalize("NFKC", name).lower()
    return _STRIP.sub("", text)


async def link_skills(db: UserDB, item_id: UUID, names: list[str]) -> None:
    seen: set[str] = set()
    for raw in names:
        name = raw.strip()
        norm = normalize_skill(name)
        if not norm or norm in seen:
            continue
        seen.add(norm)
        skill_id = await db.system.scalar(
            """insert into skills (name, normalized) values (:name, :norm)
               on conflict (normalized) do update set normalized = excluded.normalized
               returning id""",
            name=name[:100],
            norm=norm,
        )
        await db.execute(
            """insert into item_skills (item_id, skill_id, user_id)
               select i.id, cast(:skill_id as uuid), i.user_id from items i
               where i.id = :item_id and i.user_id = :user_id
               on conflict do nothing""",
            item_id=item_id,
            skill_id=skill_id,
        )


async def skills_of(db: UserDB, item_id: UUID) -> list[str]:
    rows = await db.all(
        """select s.name from item_skills isk join skills s on s.id = isk.skill_id
           where isk.item_id = :item_id and isk.user_id = :user_id order by s.name""",
        item_id=item_id,
    )
    return [r["name"] for r in rows]
