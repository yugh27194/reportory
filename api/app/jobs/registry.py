"""job 유형 → 핸들러(인계서 13.1절). 핸들러는 같은 작업을 두 번 실행해도 결과가 같아야 한다."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from app.db import UserDB
from app.jobs import (
    account,
    answer_followup,
    embed_item,
    extract_entry,
    generate_document,
    imports,
    opportunities,
    period_summary,
    process_evidence,
    recommendations,
    render_document,
)

Handler = Callable[[UserDB, dict], Awaitable[dict]]
FailureHook = Callable[[UserDB, dict], Awaitable[None]]


@dataclass
class JobSpec:
    run: Handler
    on_final_failure: FailureHook | None = None
    system: bool = False  # 사용자 없이 도는 작업(공고 수집). run은 SystemDB를 받는다


async def _noop(db: UserDB, payload: dict) -> dict:
    """Phase 0 더미 작업. payload.fail이 참이면 실패해 재시도를 시험한다."""
    if payload.get("fail"):
        raise RuntimeError("dummy failure")
    return {"ok": True}


HANDLERS: dict[str, JobSpec] = {
    "noop": JobSpec(_noop),
    "extract_entry": JobSpec(extract_entry.run, extract_entry.on_final_failure),
    "answer_followup": JobSpec(answer_followup.run),
    "embed_item": JobSpec(embed_item.run),
    "process_evidence": JobSpec(process_evidence.run, process_evidence.on_final_failure),
    "import_resume": JobSpec(imports.run_resume_job, imports.on_final_failure),
    "import_linkedin": JobSpec(imports.run_linkedin_job, imports.on_final_failure),
    "import_github": JobSpec(imports.run_github_job, imports.on_final_failure),
    "generate_document": JobSpec(generate_document.run, generate_document.on_final_failure),
    "period_summary": JobSpec(period_summary.run),
    "render_document": JobSpec(render_document.run, render_document.on_final_failure),
    "export_data": JobSpec(account.export_data),
    "delete_account": JobSpec(account.delete_account),
    "collect_opportunities": JobSpec(opportunities.collect, system=True),
    "fetch_opportunity_url": JobSpec(opportunities.fetch_url),
    "score_recommendations": JobSpec(recommendations.run),
}
