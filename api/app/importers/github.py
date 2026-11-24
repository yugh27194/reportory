"""GitHub 저장소 가져오기(인계서 10.9절).

사용자 소유 저장소를 최근 푸시 순으로 최대 30개 읽고(포크 제외), 저장소마다 project 후보 하나를 만든다.
이름·주소·언어·기간·설명은 GitHub 값을 그대로 쓰고, README가 있으면 LLM으로 요약 한두 문장을 만든다.
요약은 README에 있는 인용과 숫자만 허용한다.
"""

import base64
import logging
from datetime import date
from uuid import UUID

import httpx
from pydantic import BaseModel, Field

from app.config import get_settings
from app.db import UserDB
from app.importers.common import ImportResult, save_candidates
from app.llm.calls import call_logger
from app.llm.client import LLMError, get_llm
from app.llm.schemas import ItemCandidate
from app.llm.validators import drop_unsupported_sentences, quote_in_source
from app.services.skills import normalize_skill

log = logging.getLogger("reportory.github")

MAX_REPOS = 30
README_CHARS = 8000
TOP_LANGUAGES = 5

# 테스트에서 가짜 응답을 끼우는 자리다.
_transport: httpx.AsyncBaseTransport | None = None


def set_transport(transport: httpx.AsyncBaseTransport | None) -> None:
    global _transport
    _transport = transport


class GitHubError(Exception):
    pass


class RepoSummary(BaseModel):
    summary: str  # 한국어 서술체 1~2문장
    skills: list[str] = []
    quote: str  # README에서 그대로 복사한 근거
    confidence: float = Field(ge=0, le=1)


def _date(v: str | None) -> date | None:
    return date.fromisoformat(v[:10]) if v else None


async def fetch_repos(token: str) -> list[dict]:
    api = get_settings().github_api_url.rstrip("/")
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    async with httpx.AsyncClient(headers=headers, timeout=30.0, transport=_transport) as http:
        resp = await http.get(
            f"{api}/user/repos",
            params={"affiliation": "owner", "sort": "pushed", "per_page": 100},
        )
        if resp.status_code in (401, 403):
            raise GitHubError(
                "GitHub 권한이 없거나 만료됐다. GitHub로 다시 로그인한 뒤 시도해야 한다."
            )
        if resp.status_code >= 400:
            raise GitHubError(f"GitHub API 오류: HTTP {resp.status_code}")
        repos = [r for r in resp.json() if not r.get("fork")][:MAX_REPOS]
        out = []
        for r in repos:
            langs = await http.get(r["languages_url"])
            languages = langs.json() if langs.status_code == 200 else {}
            readme = ""
            rd = await http.get(f"{api}/repos/{r['full_name']}/readme")
            if rd.status_code == 200 and rd.json().get("content"):
                try:
                    readme = base64.b64decode(rd.json()["content"]).decode("utf-8", "replace")
                except ValueError:
                    readme = ""
            out.append({**r, "_languages": languages, "_readme": readme[:README_CHARS]})
        return out


def language_share(languages: dict[str, int]) -> list[tuple[str, int]]:
    total = sum(languages.values()) or 1
    ranked = sorted(languages.items(), key=lambda kv: kv[1], reverse=True)[:TOP_LANGUAGES]
    return [(name, round(100 * size / total)) for name, size in ranked]


async def repo_candidate(db: UserDB, repo: dict, use_llm: bool) -> ItemCandidate:
    shares = language_share(repo["_languages"])
    skills = [name for name, _ in shares]
    description = (repo.get("description") or "").strip()
    summary = description if description.endswith((".", "다")) else ""
    quote = description or repo["name"]
    confidence = 0.9
    readme = repo["_readme"]
    if use_llm and readme.strip():
        try:
            out = await get_llm().complete_json(
                "import_github",
                "import_github",
                {
                    "REPO_NAME": repo["name"],
                    "DESCRIPTION": description,
                    "LANGUAGES": dict(shares),
                    "README": readme,
                },
                RepoSummary,
                "light",
                user_id=db.user_id,
                log_call=call_logger(db),
            )
            source = f"{description}\n{readme}"
            if quote_in_source(out.quote, source):
                text, _ = drop_unsupported_sentences(out.summary, source)
                summary = text or summary
                quote = out.quote
                known = normalize_skill(source)
                skills += [
                    s for s in out.skills if normalize_skill(s) and normalize_skill(s) in known
                ]
                confidence = min(confidence, out.confidence)
        except LLMError as exc:
            log.warning("repo summary failed: %s", type(exc).__name__)
    details = {"repo_url": repo["html_url"]}
    if repo.get("homepage"):
        details["demo_url"] = repo["homepage"]
    pushed = _date(repo.get("pushed_at"))
    return ItemCandidate(
        action="create",
        type="project",
        title=repo["name"],
        start_date=_date(repo.get("created_at")),
        end_date=None,
        is_ongoing=bool(pushed and (date.today() - pushed).days <= 90),
        summary_append=summary,
        skills=list(dict.fromkeys(skills)),
        details=details,
        quote=f"GitHub {repo['full_name']}: {quote}"[:500],
        confidence=confidence,
    )


async def run_github(db: UserDB, import_id: UUID, token: str) -> ImportResult:
    result = ImportResult()
    repos = await fetch_repos(token)
    use_llm = get_settings().llm_provider != "demo"
    cands = [await repo_candidate(db, r, use_llm) for r in repos]
    result.notes["repos"] = len(repos)
    await save_candidates(db, import_id, cands, result)
    return result
