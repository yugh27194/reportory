"""주간·월간 요약(인계서 10.5절, 11.8절)."""

from datetime import date
from uuid import UUID

from app.config import get_settings
from app.db import UserDB, as_json
from app.llm.calls import call_logger
from app.llm.client import LLMError, get_llm
from app.llm.schemas import PeriodSummary
from app.llm.validators import drop_unsupported_sentences

TYPE_LABELS = {
    "education": "학력",
    "experience": "경력",
    "project": "프로젝트",
    "activity": "활동",
    "award": "수상",
    "certification": "자격증",
    "language_test": "어학",
    "publication": "논문",
}


def fallback_summary(
    entries: list[dict], changes: list[dict], period: str = "week"
) -> PeriodSummary:
    """LLM 없이 쓰는 요약: 일기 요약과 승인 항목을 목록으로 묶는다."""
    lines = [f"- {e['date'].strftime('%m/%d')} {e['summary']}" for e in entries[:8]]
    if changes:
        when = {"day": "오늘", "week": "이번 주", "month": "이번 달"}.get(period, "이 기간에")
        lines.append(f"- {when} 포트폴리오 항목 {len(changes)}개를 승인했다.")
    return PeriodSummary(
        summary_md="\n".join(lines),
        highlights=[
            {"item_id": c["id"], "text": f"{TYPE_LABELS.get(c['type'], '')} · {c['title']}"}
            for c in changes[:3]
        ],
    )


async def run(db: UserDB, payload: dict) -> dict:
    period = payload["period"]
    start = date.fromisoformat(payload["period_start"])
    end = date.fromisoformat(payload["period_end"])
    entries = await db.all(
        """select entry_date as date, summary from entries
           where user_id = :user_id and entry_date between :s and :e and summary is not null
           order by entry_date""",
        s=start,
        e=end,
    )
    if not entries:
        return {"skipped": "no_relevant_entries"}
    changes = await db.all(
        """select id, type, title, approved_at from items
           where user_id = :user_id and status = 'approved'
             and (approved_at at time zone 'Asia/Seoul')::date between :s and :e
           order by approved_at""",
        s=start,
        e=end,
    )
    # 검증 기준: 일기 요약, 승인 항목 제목, 날짜, 승인 개수(서버가 센 값).
    source = "\n".join(
        [e["summary"] for e in entries]
        + [c["title"] for c in changes]
        + [e["date"].strftime("%m/%d %Y-%m-%d") for e in entries]
        + [str(len(changes)), str(len(entries))]
    )
    result: PeriodSummary | None = None
    if get_settings().llm_provider != "demo":
        try:
            result = await get_llm().complete_json(
                "period_summary",
                "period_summary",
                {
                    "PERIOD": period,
                    "PERIOD_START": start.isoformat(),
                    "PERIOD_END": end.isoformat(),
                    "ENTRIES": [{"date": e["date"], "summary": e["summary"]} for e in entries],
                    "CHANGES": [{**c, "id": str(c["id"])} for c in changes],
                },
                PeriodSummary,
                "light",
                user_id=db.user_id,
                log_call=call_logger(db),
            )
        except LLMError:
            result = None
    if result is None:
        result = fallback_summary(entries, changes, period)
    # 줄마다(목록 항목마다) 따로 검증해, 근거 없는 숫자가 든 줄만 지운다.
    kept = []
    for line in result.summary_md.splitlines():
        stripped = line.strip()
        bullet = stripped.startswith(("- ", "* "))
        text, _ = drop_unsupported_sentences(stripped[2:] if bullet else stripped, source)
        if text.strip():
            kept.append(f"- {text}" if bullet else text)
    summary_md = "\n".join(kept)
    allowed = {c["id"] for c in changes}
    highlights = [
        {"item_id": str(h.item_id), "text": h.text}
        for h in result.highlights
        if h.item_id in allowed
    ][:3]
    summary_id: UUID = await db.scalar(
        """insert into period_summaries (user_id, period, period_start, period_end, summary_md,
             highlights)
           values (:user_id, cast(:p as period_type), :s, :e, :md, cast(:h as jsonb))
           on conflict (user_id, period, period_start) do update
             set summary_md = excluded.summary_md, highlights = excluded.highlights,
                 period_end = excluded.period_end
           returning id""",
        p=period,
        s=start,
        e=end,
        md=summary_md or "이 기간의 기록을 요약하지 못했다.",
        h=as_json(highlights),
    )
    if period == "day":
        title = f"{start.strftime('%m/%d')} 하루 요약이 나왔다."
    else:
        label = "주간" if period == "week" else "월간"
        title = f"{start.strftime('%m/%d')}~{end.strftime('%m/%d')} {label} 요약이 나왔다."
    await db.execute(
        """insert into notifications (user_id, type, title, link, ref_id)
           values (:user_id, 'summary_ready', :title, '/summaries', :ref)
           on conflict do nothing""",
        title=title,
        ref=summary_id,
    )
    return {"summary_id": str(summary_id), "entries": len(entries), "changes": len(changes)}
