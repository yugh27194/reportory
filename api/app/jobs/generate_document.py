"""문서 버전 생성(인계서 10.8절, 11.5절): 항목 → 문장 변환·검증 → JSON Resume → HTML → PDF."""

from uuid import UUID

from app.config import get_settings
from app.db import UserDB, as_json
from app.llm.calls import call_logger
from app.llm.client import LLMError, get_llm
from app.llm.schemas import RewriteResult
from app.llm.validators import numbers_supported
from app.services.documents import (
    FORMAT_RULES,
    RESUME_EN_MAX_BULLETS,
    build_content,
    fallback_lines,
    item_source_text,
    load_items,
    validate_sections,
)
from app.services.render import RenderError, page_count, render_html, render_pdf
from app.storage import get_storage


async def rewrite(
    db: UserDB, fmt: str, items: list[dict], target: str | None, warnings: list[str]
) -> tuple[dict[str, dict], str | None, int]:
    by_id = {str(i["id"]): i for i in items}
    fallback = {str(i["id"]): {"heading": None, "lines": fallback_lines(i)} for i in items}
    if get_settings().llm_provider == "demo":
        if fmt == "resume_en":
            warnings.append("데모 분석에서는 문장을 영어로 바꾸지 않는다. 항목 요약을 그대로 썼다.")
        return fallback, None, 0
    variables = {
        "FORMAT": fmt,
        "FORMAT_RULES": FORMAT_RULES[fmt],
        "TARGET": target or "",
        "LANGUAGE": "en" if fmt == "resume_en" else "ko",
        "ITEMS": [
            {
                "id": str(i["id"]),
                "type": i["type"],
                "title": i["title"],
                "title_en": i.get("title_en"),
                "organization": i.get("organization"),
                "role": i.get("role"),
                "period": [i.get("start_date"), i.get("end_date")],
                "summary": i.get("summary"),
                "metrics": i.get("metrics"),
                "details": i.get("details"),
                "skills": i.get("skills"),
                "quotes": i.get("quotes", [])[:10],
            }
            for i in items
        ],
    }
    try:
        out = await get_llm().complete_json(
            "rewrite_document",
            "rewrite_document",
            variables,
            RewriteResult,
            "extract",
            user_id=db.user_id,
            log_call=call_logger(db),
        )
    except LLMError:
        warnings.append("문장 다듬기에 실패해 항목 요약을 그대로 썼다.")
        return fallback, None, 0
    lines, dropped = validate_sections(
        out.sections, by_id, RESUME_EN_MAX_BULLETS if fmt == "resume_en" else None
    )
    summary = out.summary if fmt == "resume_en" else None
    if summary and not numbers_supported(summary, "\n".join(item_source_text(i) for i in items)):
        summary = None
        dropped += 1
    return lines, summary, dropped


async def run(db: UserDB, payload: dict) -> dict:
    version_id = UUID(payload["version_id"])
    v = await db.one(
        """select v.id, v.selected_item_ids, v.options, d.format, d.title, d.target_description
           from document_versions v join documents d on d.id = v.document_id
           where v.id = :id and v.user_id = :user_id""",
        id=version_id,
    )
    if v is None:
        return {"skipped": "version_deleted"}
    await db.execute(
        "update document_versions set status = 'running' where id = :id and user_id = :user_id",
        id=version_id,
    )
    profile = (
        await db.one(
            """select display_name, display_name_en, headline, email_public, links, interests
           from profiles where id = :user_id"""
        )
        or {}
    )
    fmt = v["format"]
    items = await load_items(db, list(v["selected_item_ids"]))
    warnings: list[str] = []
    lines, summary, dropped = await rewrite(db, fmt, items, v["target_description"], warnings)
    if dropped:
        warnings.append(f"근거에 없는 숫자가 든 문장 {dropped}개를 지웠다.")

    def build(selected: list[dict]) -> dict:
        content = build_content(fmt, profile, selected, lines)
        if summary:
            content["x-summary"] = summary
        return content

    content = build(items)
    pdf: bytes | None = None
    removed: list[str] = []
    try:
        pdf = await render_pdf(render_html(fmt, content, title=v["title"], for_pdf=True))
        # 영문 Resume는 A4 1쪽을 넘지 않게, 순위가 낮은(뒤쪽) 항목부터 뺀다.
        while fmt == "resume_en" and page_count(pdf) > 1 and len(items) > 1:
            removed.append(items.pop()["title"])
            content = build(items)
            pdf = await render_pdf(render_html(fmt, content, title=v["title"], for_pdf=True))
    except RenderError as exc:
        warnings.append(str(exc))
    if removed:
        warnings.append(f"1쪽에 맞추려고 항목 {len(removed)}개를 뺐다: {', '.join(removed)}")

    pdf_path = None
    if pdf:
        pdf_path = f"{db.user_id}/{version_id}.pdf"
        await get_storage().put("documents", pdf_path, pdf, "application/pdf")
    options = {
        **(v["options"] or {}),
        "warnings": warnings,
        "dropped_lines": dropped,
        "removed_items": removed,
    }
    await db.execute(
        """update document_versions set status = 'succeeded', content = cast(:c as jsonb),
             pdf_path = :pdf, options = cast(:o as jsonb)
           where id = :id and user_id = :user_id""",
        id=version_id,
        c=as_json(content),
        pdf=pdf_path,
        o=as_json(options),
    )
    return {"pdf": bool(pdf_path), "warnings": len(warnings), "dropped_lines": dropped}


async def on_final_failure(db: UserDB, payload: dict) -> None:
    await db.execute(
        "update document_versions set status = 'failed' where id = :id and user_id = :user_id",
        id=UUID(payload["version_id"]),
    )
