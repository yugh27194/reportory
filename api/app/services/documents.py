"""목적별 문서(인계서 10.8절, 11.5절): 형식 규칙, 항목 순위, 숫자 검증, JSON Resume 내용."""

import math
from datetime import date
from typing import Any
from uuid import UUID

from app.db import UserDB
from app.llm.schemas import DocSection
from app.llm.validators import numbers_supported

# 형식별 섹션: (키, 국문 제목, 영문 제목, 항목 유형)
SECTIONS: dict[str, list[tuple[str, str, str, tuple[str, ...]]]] = {
    "academic_cv": [
        ("education", "학력", "Education", ("education",)),
        ("research", "연구 경험", "Research Experience", ("experience",)),
        ("publications", "논문·발표", "Publications", ("publication",)),
        ("awards", "수상·장학", "Awards & Scholarships", ("award",)),
        ("projects", "프로젝트", "Projects", ("project",)),
        ("activities", "활동", "Activities", ("activity",)),
        ("certifications", "자격증", "Certifications", ("certification",)),
        ("languages", "어학", "Languages", ("language_test",)),
    ],
    "resume_en": [
        ("education", "학력", "Education", ("education",)),
        ("experience", "경력", "Experience", ("experience",)),
        ("projects", "프로젝트", "Projects", ("project", "activity")),
        ("awards", "수상", "Awards", ("award",)),
        ("certifications", "자격증", "Certifications", ("certification", "language_test")),
    ],
    "resume_ko": [
        ("education", "학력", "Education", ("education",)),
        ("experience", "경력", "Experience", ("experience",)),
        ("certifications", "자격증", "Certifications", ("certification",)),
        ("languages", "어학", "Languages", ("language_test",)),
        ("awards", "수상", "Awards", ("award",)),
        ("activities", "대외활동", "Activities", ("activity",)),
        ("projects", "프로젝트", "Projects", ("project",)),
    ],
    "project_portfolio": [
        ("projects", "프로젝트", "Projects", ("project", "activity", "experience")),
    ],
}

FORMAT_LABELS = {
    "academic_cv": "Academic CV",
    "resume_en": "영문 Resume",
    "resume_ko": "국문 이력서",
    "project_portfolio": "프로젝트 포트폴리오",
    "web_profile": "공개 웹 프로필",
}

# 형식별 유형 우선순위(0~1). 순위 계산과 기본 선택에 쓴다.
TYPE_PRIORITY: dict[str, dict[str, float]] = {
    "academic_cv": {
        "experience": 1.0,
        "publication": 1.0,
        "education": 0.9,
        "award": 0.8,
        "project": 0.6,
        "activity": 0.4,
        "certification": 0.3,
        "language_test": 0.3,
    },
    "resume_en": {
        "experience": 1.0,
        "project": 0.9,
        "education": 0.8,
        "award": 0.6,
        "certification": 0.4,
        "language_test": 0.4,
        "activity": 0.5,
    },
    "resume_ko": {
        "experience": 1.0,
        "education": 0.9,
        "certification": 0.8,
        "language_test": 0.8,
        "award": 0.7,
        "activity": 0.6,
        "project": 0.7,
    },
    "project_portfolio": {"project": 1.0, "activity": 0.4, "experience": 0.5},
}
DEFAULT_PICK = {"academic_cv": 30, "resume_en": 8, "resume_ko": 30, "project_portfolio": 4}
RESUME_EN_MAX_BULLETS = 4

FORMAT_RULES = {
    "academic_cv": "대학원·연구실 지원용 Academic CV다. 연구 경험을 앞세우고, 항목마다 한 일과 결과를 "
    "한국어 서술체 1~3문장으로 쓴다.",
    "resume_en": "Write in English. Each item has at most 4 bullet lines. Every bullet starts "
    "with a past-tense action verb (Built, Led, Designed...). Keep each bullet under 25 words.",
    "resume_ko": "국내 기업·공공기관 지원용 국문 이력서다. 항목마다 한 일과 결과를 한국어 서술체 "
    "1~2문장으로 짧게 쓴다.",
    "project_portfolio": "개발·데이터 직무용 프로젝트 포트폴리오다. 프로젝트마다 배경, 내 역할·팀 구성, "
    "방법·도구, 결과를 한 줄씩 한국어 서술체로 쓴다. 근거에 없는 줄은 쓰지 않는다.",
}


def item_types_for(fmt: str) -> set[str]:
    return {t for _, _, _, types in SECTIONS[fmt] for t in types}


def _recency(item: dict) -> float:
    d = item.get("end_date") or item.get("start_date")
    if item.get("is_ongoing"):
        return 1.0
    if not d:
        return 0.3
    months = max(0, (date.today() - d).days / 30)
    return math.pow(0.5, months / 24)


async def rank_items(db: UserDB, fmt: str, target_vec: list[float] | None) -> list[dict]:
    """대상 설명 유사도(임베딩이 있을 때), 최신성, 형식별 유형 우선순위로 순위를 매긴다."""
    types = list(item_types_for(fmt))
    sim_sql = (
        "case when embedding is null then null else 1 - (embedding <=> cast(:v as vector)) end"
        if target_vec
        else "null"
    )
    params: dict[str, Any] = {"types": types}
    if target_vec:
        params["v"] = str(target_vec)
    rows = await db.all(
        f"""select id, type, title, title_en, organization, start_date, end_date, is_ongoing,
                   {sim_sql} as sim
            from items where user_id = :user_id and status = 'approved'
              and type = any(cast(:types as item_type[]))""",
        **params,
    )
    prio = TYPE_PRIORITY[fmt]
    for r in rows:
        sim = r.pop("sim")
        r["score"] = round(
            (0.5 * sim if sim is not None else 0.0)
            + 0.3 * prio.get(r["type"], 0.2)
            + 0.2 * _recency(r),
            4,
        )
    rows.sort(key=lambda r: r["score"], reverse=True)
    limit = DEFAULT_PICK[fmt]
    picked = 0
    for r in rows:
        default = picked < limit and (fmt != "project_portfolio" or r["type"] == "project")
        r["selected"] = default
        picked += default
    return rows


def item_source_text(item: dict) -> str:
    """문장 검증 기준: 항목 요약·수치·세부·날짜·근거 인용."""
    parts = [
        item["title"],
        item.get("title_en") or "",
        item.get("organization") or "",
        item.get("role") or "",
        item.get("summary") or "",
    ]
    parts += [f"{m.get('name')} {m.get('value')} {m.get('unit') or ''}" for m in item["metrics"]]
    parts += [str(v) for v in (item.get("details") or {}).values()]
    parts += [str(d) for d in (item.get("start_date"), item.get("end_date")) if d]
    parts += [q for q in item.get("quotes", []) if q]
    return "\n".join(parts)


def validate_sections(
    sections: list[DocSection], items: dict[str, dict], max_lines: int | None = None
) -> tuple[dict[str, dict], int]:
    """item_id가 선택된 항목인지, 문장 안 숫자가 그 항목 근거에 있는지 확인한다.

    돌려주는 값: item_id → {heading, lines}, 지운 문장 수.
    """
    out: dict[str, dict] = {}
    dropped = 0
    for sec in sections:
        key = str(sec.item_id)
        if key not in items:
            dropped += len(sec.lines)
            continue
        source = item_source_text(items[key])
        entry = out.setdefault(key, {"heading": sec.heading, "lines": []})
        for line in sec.lines:
            text = line.text.strip()
            if str(line.item_id) != key or not text:
                dropped += 1
            elif not numbers_supported(text, source):
                dropped += 1
            else:
                entry["lines"].append(text)
        if max_lines is not None and len(entry["lines"]) > max_lines:
            dropped += len(entry["lines"]) - max_lines
            entry["lines"] = entry["lines"][:max_lines]
    return out, dropped


def fallback_lines(item: dict) -> list[str]:
    """LLM 없이(데모) 쓰는 문장: 항목 요약을 문장 단위로 나눈다."""
    from app.llm.demo import sentences

    return sentences(item.get("summary") or "")[:4]


def _period(item: dict) -> tuple[str | None, str | None]:
    s = item.get("start_date")
    e = item.get("end_date")
    return (
        s.isoformat() if s else None,
        None if item.get("is_ongoing") else (e.isoformat() if e else None),
    )


def build_content(fmt: str, profile: dict, items: list[dict], lines: dict[str, dict]) -> dict:
    """JSON Resume(https://jsonresume.org/schema) 형식과 x-reportory 확장."""
    en = fmt == "resume_en"

    def name(i: dict) -> str:
        return (i.get("title_en") or i["title"]) if en else i["title"]

    def hl(i: dict) -> list[str]:
        return lines.get(str(i["id"]), {}).get("lines", [])

    by_type: dict[str, list[dict]] = {}
    for i in items:
        by_type.setdefault(i["type"], []).append(i)
    content: dict[str, Any] = {
        "basics": {
            "name": (profile.get("display_name_en") if en else profile.get("display_name")) or "",
            "label": profile.get("headline") or "",
            "email": profile.get("email_public") or "",
            "profiles": [
                {"network": link["label"], "url": link["url"]}
                for link in profile.get("links") or []
            ],
        },
        "work": [],
        "education": [],
        "awards": [],
        "certificates": [],
        "projects": [],
        "publications": [],
        "languages": [],
        "volunteer": [],
        "skills": [],
    }
    for i in by_type.get("experience", []):
        start, end = _period(i)
        content["work"].append(
            {
                "name": i.get("organization") or "",
                "position": i.get("role") or name(i),
                "startDate": start,
                "endDate": end,
                "highlights": hl(i),
                "x-itemId": str(i["id"]),
            }
        )
    for i in by_type.get("education", []):
        start, end = _period(i)
        d = i.get("details") or {}
        content["education"].append(
            {
                "institution": name(i),
                "area": d.get("major") or "",
                "studyType": d.get("degree") or "",
                "startDate": start,
                "endDate": end,
                "score": d.get("gpa") or "",
                "courses": hl(i),
                "x-itemId": str(i["id"]),
            }
        )
    for i in by_type.get("award", []):
        d = i.get("details") or {}
        content["awards"].append(
            {
                "title": name(i),
                "awarder": d.get("host") or i.get("organization") or "",
                "date": _period(i)[1] or _period(i)[0],
                "summary": " ".join(hl(i)),
                "x-rank": d.get("rank"),
                "x-itemId": str(i["id"]),
            }
        )
    for i in by_type.get("certification", []):
        d = i.get("details") or {}
        content["certificates"].append(
            {
                "name": name(i),
                "issuer": d.get("issuer") or i.get("organization") or "",
                "date": _period(i)[0],
                "x-itemId": str(i["id"]),
            }
        )
    for i in by_type.get("language_test", []):
        d = i.get("details") or {}
        content["languages"].append(
            {
                "language": d.get("test") or name(i),
                "fluency": d.get("score") or d.get("level") or "",
                "x-testDate": d.get("test_date"),
                "x-validUntil": d.get("valid_until"),
                "x-itemId": str(i["id"]),
            }
        )
    for i in by_type.get("publication", []):
        d = i.get("details") or {}
        content["publications"].append(
            {
                "name": name(i),
                "publisher": d.get("venue") or "",
                "releaseDate": _period(i)[1] or _period(i)[0],
                "url": d.get("doi") or "",
                "summary": " ".join(hl(i)),
                "x-authors": d.get("authors"),
                "x-itemId": str(i["id"]),
            }
        )
    for t in ("project", "activity"):
        for i in by_type.get(t, []):
            start, end = _period(i)
            d = i.get("details") or {}
            target = "projects" if t == "project" or fmt != "resume_ko" else "volunteer"
            entry = {
                "name": name(i),
                "description": i.get("organization") or "",
                "startDate": start,
                "endDate": end,
                "highlights": hl(i),
                "url": d.get("demo_url") or d.get("repo_url") or "",
                "roles": [i["role"]] if i.get("role") else [],
                "keywords": i.get("skills", []),
                "x-itemId": str(i["id"]),
            }
            if target == "volunteer":
                entry = {
                    "organization": i.get("organization") or name(i),
                    "position": i.get("role") or "",
                    "startDate": start,
                    "endDate": end,
                    "highlights": hl(i),
                    "x-title": name(i),
                    "x-itemId": str(i["id"]),
                }
            content[target].append(entry)
    skills: dict[str, None] = {}
    for i in items:
        for s in i.get("skills", []):
            skills.setdefault(s, None)
    if skills:
        content["skills"] = [{"name": "Skills" if en else "기술", "keywords": list(skills)}]
    content["x-reportory"] = {
        "format": fmt,
        "language": "en" if en else "ko",
        "sections": [
            {
                "key": k,
                "label": en_label if en else ko_label,
                "items": [str(i["id"]) for i in items if i["type"] in types],
            }
            for k, ko_label, en_label, types in SECTIONS[fmt]
        ],
        "items": {
            str(i["id"]): {
                "title": name(i),
                "type": i["type"],
                "organization": i.get("organization"),
                "role": i.get("role"),
                "period": _period(i),
                "is_ongoing": i.get("is_ongoing"),
                "skills": i.get("skills", []),
                "metrics": i.get("metrics", []),
                "details": i.get("details") or {},
                "heading": lines.get(str(i["id"]), {}).get("heading"),
                "lines": hl(i),
            }
            for i in items
        },
        "interests": profile.get("interests") or [],
    }
    return content


async def load_items(db: UserDB, ids: list[UUID]) -> list[dict]:
    """선택 순서를 지킨 승인 항목 목록(기술, 근거 인용 포함)."""
    rows = await db.all(
        """select id, type, title, title_en, organization, role, start_date, end_date, is_ongoing,
                  summary, details, metrics, links
           from items where user_id = :user_id and status = 'approved' and id = any(:ids)""",
        ids=ids,
    )
    by_id = {r["id"]: r for r in rows}
    out = []
    for i in ids:
        r = by_id.get(i)
        if r is None:
            continue
        r["skills"] = [
            s["name"]
            for s in await db.all(
                """select s.name from item_skills isk join skills s on s.id = isk.skill_id
               where isk.item_id = :id and isk.user_id = :user_id order by s.name""",
                id=i,
            )
        ]
        r["quotes"] = [
            q["quote"]
            for q in await db.all(
                """select quote from item_sources where item_id = :id and user_id = :user_id
                 and quote is not null order by created_at""",
                id=i,
            )
        ]
        out.append(r)
    return out
