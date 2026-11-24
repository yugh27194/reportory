"""LinkedIn 데이터 내보내기 ZIP 가져오기(인계서 10.9절). CSV는 구조화돼 있어 LLM 없이 규칙으로 만든다.

열 이름 기준으로 읽고, 열 이름이 다르거나 파일이 없으면 건너뛰고 요약에 남긴다.
"""

import csv
import io
import re
import zipfile
from datetime import date
from uuid import UUID

from app.db import UserDB
from app.importers.common import ImportResult, save_candidates
from app.llm.schemas import ItemCandidate
from app.services.privacy import scrub

RULE_CONFIDENCE = 0.9

_MONTHS = {
    m: i
    for i, m in enumerate(
        ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"],
        start=1,
    )
}


def parse_date(value: str | None) -> date | None:
    """LinkedIn 날짜("Mar 2023", "2023-03", "2023", "3월 2023")를 그 달 1일로 바꾼다."""
    if not value or not value.strip():
        return None
    v = value.strip()
    m = re.fullmatch(r"([A-Za-z]{3})[a-z]*\.? (\d{4})", v)
    if m and m.group(1).lower() in _MONTHS:
        return date(int(m.group(2)), _MONTHS[m.group(1).lower()], 1)
    m = re.fullmatch(r"(\d{4})[-./](\d{1,2})(?:[-./]\d{1,2})?", v)
    if m:
        return date(int(m.group(1)), int(m.group(2)), 1)
    m = re.fullmatch(r"(\d{1,2})월 (\d{4})", v)
    if m:
        return date(int(m.group(2)), int(m.group(1)), 1)
    m = re.fullmatch(r"(\d{4})", v)
    if m:
        return date(int(m.group(1)), 1, 1)
    return None


def _read(z: zipfile.ZipFile, name: str) -> list[dict[str, str]] | None:
    match = next((n for n in z.namelist() if n.split("/")[-1].lower() == name.lower()), None)
    if match is None:
        return None
    raw = z.read(match).decode("utf-8-sig", errors="replace")
    return [
        {k.strip(): (v or "").strip() for k, v in row.items() if k}
        for row in csv.DictReader(io.StringIO(raw))
    ]


def _need(rows: list[dict], cols: list[str]) -> bool:
    return bool(rows) and all(c in rows[0] for c in cols)


def _cand(**kw) -> ItemCandidate:
    return ItemCandidate(action="create", confidence=RULE_CONFIDENCE, **kw)


def _quote(file: str, *parts: str) -> str:
    return f"{file}: " + " / ".join(p for p in parts if p)


def _summary(text: str) -> str:
    return (scrub(text) or "")[:600]


def candidates_from_zip(data: bytes, result: ImportResult) -> list[ItemCandidate]:
    cands: list[ItemCandidate] = []
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        handlers = [
            ("Positions.csv", ["Company Name", "Title"], _positions),
            ("Education.csv", ["School Name"], _education),
            ("Certifications.csv", ["Name"], _certifications),
            ("Projects.csv", ["Title"], _projects),
            ("Languages.csv", ["Name"], _languages),
        ]
        for name, cols, fn in handlers:
            rows = _read(z, name)
            if rows is None:
                result.skipped.append(f"{name}: 파일이 없어 건너뜀")
            elif rows and not _need(rows, cols):
                result.skipped.append(f"{name}: 열 이름이 달라 건너뜀")
            else:
                cands.extend(fn(rows))
        skills = _read(z, "Skills.csv")
        if skills is None:
            result.skipped.append("Skills.csv: 파일이 없어 건너뜀")
        elif skills and "Name" in skills[0]:
            result.notes["skills"] = [r["Name"] for r in skills if r.get("Name")][:100]
        profile = _read(z, "Profile.csv")
        if profile is None:
            result.skipped.append("Profile.csv: 파일이 없어 건너뜀")
        elif profile and profile[0].get("Headline"):
            result.notes["headline"] = profile[0]["Headline"][:120]
    return cands


def _positions(rows):
    for r in rows:
        if not r.get("Title"):
            continue
        end = parse_date(r.get("Finished On"))
        yield _cand(
            type="experience",
            title=r["Title"],
            organization=r.get("Company Name") or None,
            role=r["Title"],
            start_date=parse_date(r.get("Started On")),
            end_date=end,
            is_ongoing=end is None and bool(r.get("Started On")),
            summary_append=_summary(r.get("Description", "")),
            quote=_quote("Positions.csv", r.get("Company Name", ""), r["Title"]),
        )


def _education(rows):
    for r in rows:
        if not r.get("School Name"):
            continue
        details = {k: v for k, v in {"degree": r.get("Degree Name")}.items() if v}
        yield _cand(
            type="education",
            title=r["School Name"],
            organization=r["School Name"],
            start_date=parse_date(r.get("Start Date")),
            end_date=parse_date(r.get("End Date")),
            details=details,
            summary_append=_summary(r.get("Notes", "")),
            quote=_quote("Education.csv", r["School Name"], r.get("Degree Name", "")),
        )


def _certifications(rows):
    for r in rows:
        if not r.get("Name"):
            continue
        # License Number(자격증 번호 전체)는 저장하지 않는다.
        details = {"issuer": r["Authority"]} if r.get("Authority") else {}
        yield _cand(
            type="certification",
            title=r["Name"],
            organization=r.get("Authority") or None,
            start_date=parse_date(r.get("Started On")),
            end_date=parse_date(r.get("Finished On")),
            details=details,
            quote=_quote("Certifications.csv", r["Name"], r.get("Authority", "")),
        )


def _projects(rows):
    for r in rows:
        if not r.get("Title"):
            continue
        end = parse_date(r.get("Finished On"))
        details = {"repo_url": r["Url"]} if r.get("Url", "").startswith("http") else {}
        yield _cand(
            type="project",
            title=r["Title"],
            start_date=parse_date(r.get("Started On")),
            end_date=end,
            summary_append=_summary(r.get("Description", "")),
            details=details,
            quote=_quote("Projects.csv", r["Title"]),
        )


def _languages(rows):
    for r in rows:
        if not r.get("Name"):
            continue
        details = {
            "test": r["Name"],
            **({"level": r["Proficiency"]} if r.get("Proficiency") else {}),
        }
        yield _cand(
            type="language_test",
            title=r["Name"],
            details=details,
            quote=_quote("Languages.csv", r["Name"], r.get("Proficiency", "")),
        )


async def run_linkedin(db: UserDB, import_id: UUID, data: bytes) -> ImportResult:
    result = ImportResult()
    cands = candidates_from_zip(data, result)
    await save_candidates(db, import_id, list(cands), result)
    return result
