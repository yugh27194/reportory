"""고친 문서 버전 다시 그리기: 내용은 그대로 두고 HTML → PDF만 만든다(LLM을 부르지 않는다)."""

from uuid import UUID

from app.db import UserDB, as_json
from app.services.render import RenderError, page_count, render_html, render_pdf
from app.storage import get_storage


async def run(db: UserDB, payload: dict) -> dict:
    version_id = UUID(payload["version_id"])
    v = await db.one(
        """select v.id, v.content, v.options, d.format, d.title
           from document_versions v join documents d on d.id = v.document_id
           where v.id = :id and v.user_id = :user_id""",
        id=version_id,
    )
    if v is None or not v["content"]:
        return {"skipped": "version_missing"}
    warnings: list[str] = []
    pdf_path = None
    try:
        pdf = await render_pdf(
            render_html(v["format"], v["content"], title=v["title"], for_pdf=True)
        )
        if v["format"] == "resume_en" and page_count(pdf) > 1:
            warnings.append("고친 내용이 1쪽을 넘는다. 문장을 줄이거나 항목을 빼면 1쪽에 맞는다.")
        pdf_path = f"{db.user_id}/{version_id}.pdf"
        await get_storage().put("documents", pdf_path, pdf, "application/pdf")
    except RenderError as exc:
        warnings.append(str(exc))
    options = {**(v["options"] or {}), "warnings": warnings}
    await db.execute(
        """update document_versions set status = 'succeeded', pdf_path = :pdf,
             options = cast(:o as jsonb)
           where id = :id and user_id = :user_id""",
        id=version_id,
        pdf=pdf_path,
        o=as_json(options),
    )
    return {"pdf": bool(pdf_path)}


async def on_final_failure(db: UserDB, payload: dict) -> None:
    await db.execute(
        "update document_versions set status = 'failed' where id = :id and user_id = :user_id",
        id=UUID(payload["version_id"]),
    )
