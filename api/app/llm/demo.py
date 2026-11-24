"""데모 분석(LLM_PROVIDER=demo). 외부 API 없이 규칙으로 후보를 만든다.

API 키 없이 로그인·DB·워커·화면 연결을 확인하기 위한 모드다. 분석 품질은 실제 LLM보다 훨씬
낮고, 일기 문장을 그대로 제목·인용으로 쓰며 수치·날짜는 만들지 않는다. 출력은 실제 LLM과 같은
스키마 검증과 서버 검증(validators)을 그대로 거친다.
"""

import re
from typing import Any

from app.services.skills import normalize_skill

DEMO_CONFIDENCE = 0.6  # 0.8 미만이라 일괄 승인되지 않고 하나씩 확인하게 된다

# (유형, 문장에 있으면 그 유형으로 보는 표현). 위에서부터 먼저 맞는 것을 쓴다.
TYPE_RULES: list[tuple[str, re.Pattern[str]]] = [
    ("award", re.compile(r"대상|최우수상|우수상|장려상|금상|은상|동상|입상|수상")),
    ("language_test", re.compile(r"토익|TOEIC|토플|TOEFL|오픽|OPIc|텝스|TEPS|IELTS", re.I)),
    (
        "certification",
        re.compile(r"자격증|산업기사|기능사|정보처리기사|SQLD|ADsP|기사 (필기|실기)"),
    ),
    ("publication", re.compile(r"논문|투고|게재|학회 발표")),
    ("experience", re.compile(r"인턴|학부연구생|연구실")),
    ("project", re.compile(r"프로젝트|해커톤|공모전|개발|구현")),
    ("activity", re.compile(r"동아리|봉사|서포터즈|대외활동|멘토링|스터디")),
]

KNOWN_SKILLS = [
    "Python",
    "Java",
    "JavaScript",
    "TypeScript",
    "C++",
    "C#",
    "Go",
    "Kotlin",
    "Swift",
    "SQL",
    "React",
    "Next.js",
    "Vue",
    "Node.js",
    "Spring",
    "Django",
    "FastAPI",
    "Flask",
    "PyTorch",
    "TensorFlow",
    "scikit-learn",
    "Pandas",
    "Docker",
    "Kubernetes",
    "AWS",
    "GCP",
    "PostgreSQL",
    "MySQL",
    "MongoDB",
    "Git",
    "Figma",
    "Unity",
]

_SENTENCE = re.compile(r"(?<=[.!?。])\s+|\n+")
_TITLE_MAX = 40


def sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE.split(text) if s and s.strip()]


def skills_in(text: str) -> list[str]:
    norm = normalize_skill(text)
    return [s for s in KNOWN_SKILLS if normalize_skill(s) in norm]


def _title(sentence: str) -> str:
    t = sentence.rstrip(".!?。 ")
    return t if len(t) <= _TITLE_MAX else t[: _TITLE_MAX - 1] + "…"


def extract_entry(variables: dict[str, Any]) -> dict[str, Any]:
    body: str = variables["ENTRY"]
    known: list[dict] = variables.get("KNOWN_ITEMS") or []
    items: list[dict[str, Any]] = []
    used_types: set[str] = set()
    linked: set[str] = set()
    for sentence in sentences(body):
        norm = normalize_skill(sentence)
        target = next(
            (
                k
                for k in known
                if len(normalize_skill(k["title"])) >= 2 and normalize_skill(k["title"]) in norm
            ),
            None,
        )
        if target and target["id"] not in linked:
            linked.add(target["id"])
            items.append(
                {
                    "action": "link",
                    "target_item_id": target["id"],
                    "type": target["type"],
                    "title": target["title"],
                    "quote": sentence,
                    "confidence": DEMO_CONFIDENCE,
                }
            )
            continue
        item_type = next((t for t, rule in TYPE_RULES if rule.search(sentence)), None)
        if item_type is None or item_type in used_types:
            continue
        used_types.add(item_type)
        items.append(
            {
                "action": "create",
                "type": item_type,
                "title": _title(sentence),
                "summary_append": sentence if sentence.endswith((".", "다")) else "",
                "skills": skills_in(sentence),
                "quote": sentence,
                "confidence": DEMO_CONFIDENCE,
            }
        )
    first = sentences(body)[0] if body.strip() else ""
    return {"is_relevant": bool(items), "entry_summary": first if items else "", "items": items}


def answer_followup(variables: dict[str, Any]) -> dict[str, Any]:
    item, answer = variables["ITEM"], variables["ANSWER"]
    first = sentences(answer)[0]
    return {
        "action": "update",
        "target_item_id": item["id"],
        "type": item["type"],
        "title": item["title"],
        "summary_append": first if first.endswith((".", "다")) else "",
        "skills": skills_in(answer),
        "quote": first,
        "confidence": DEMO_CONFIDENCE,
    }


HANDLERS = {"extract_entry": extract_entry, "answer_followup": answer_followup}


# ===== 증빙(데모): 파일 이름과 PDF 글자에서 규칙으로 읽는다. 스캔본·이미지는 읽지 못한다. =====
_TESTS = ["TOEIC Speaking", "TOEIC", "TOEFL", "TEPS", "OPIc", "IELTS", "JLPT", "HSK"]
_DATE = re.compile(r"(20\d{2})\s*[.\-/년]\s*(\d{1,2})\s*[.\-/월]\s*(\d{1,2})")
_SCORE = re.compile(r"(?:Total|TOTAL|총점|점수|Score|SCORE)\D{0,12}(\d{2,3})")
_RANK = re.compile(r"(대상|최우수상|우수상|장려상|금상|은상|동상|입선)")


def process_evidence(variables: dict[str, Any]) -> dict[str, Any]:
    text: str = variables.get("TEXT") or ""
    source = f"{variables.get('FILE_NAME') or ''}\n{text}"
    if not text.strip():
        return {"kind": "other", "confidence": 0.2}
    test = next((t for t in _TESTS if t.lower() in source.lower()), None)
    date_m = _DATE.search(text)
    issued = (
        f"{date_m.group(1)}-{int(date_m.group(2)):02d}-{int(date_m.group(3)):02d}"
        if date_m
        else None
    )
    if test:
        score = _SCORE.search(text)
        return {
            "kind": "language_score",
            "title": test,
            "score": score.group(1) if score else None,
            "issued_on": issued,
            "confidence": 0.5,
        }
    rank = _RANK.search(text)
    if rank or "상장" in source:
        return {
            "kind": "award_certificate",
            "title": None,
            "award_rank": rank.group(1) if rank else None,
            "issued_on": issued,
            "confidence": 0.4,
        }
    if "수료" in source:
        return {"kind": "completion_certificate", "issued_on": issued, "confidence": 0.4}
    if "자격" in source or "기사" in source:
        return {"kind": "certificate", "issued_on": issued, "confidence": 0.4}
    return {"kind": "other", "issued_on": issued, "confidence": 0.3}


HANDLERS["process_evidence"] = process_evidence
HANDLERS["import_resume"] = extract_entry
