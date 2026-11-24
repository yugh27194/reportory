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
        if item_type is None:
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


# ----- 활동 추천(Phase 3) -----
_CATEGORY_RULES = [
    ("hackathon", re.compile(r"해커톤|hackathon", re.I)),
    ("research_internship", re.compile(r"학부연구생|연구\s*인턴|연구실 인턴")),
    ("internship", re.compile(r"인턴")),
    ("scholarship", re.compile(r"장학")),
    ("contest", re.compile(r"공모전|경진대회|챌린지")),
    ("education", re.compile(r"부트캠프|교육생|아카데미")),
    ("external_activity", re.compile(r"서포터즈|기자단|대외활동|봉사단|앰배서더")),
]
_DATE = re.compile(r"(20\d{2})\s*[.\-/년]\s*(\d{1,2})\s*[.\-/월]\s*(\d{1,2})")


def normalize_opportunity(variables: dict[str, Any]) -> dict[str, Any]:
    """규칙 기반 공고 정리: 모집 표현이 있으면 공고로 보고, '마감'·'접수' 근처 날짜를 마감일로 쓴다."""
    page = str(variables.get("PAGE", ""))
    title = str(variables.get("PAGE_TITLE") or "").split("|")[0].split(" - ")[0].strip()
    is_opp = bool(re.search(r"모집|공모|참가자|지원\s*자격|선발", page))
    category = next(
        (c for c, rx in _CATEGORY_RULES if rx.search(title + " " + page[:2000])), "other"
    )
    deadline = None
    for line in page.splitlines():
        if re.search(r"마감|접수\s*기간|모집\s*기간|신청\s*기간", line):
            dates = _DATE.findall(line)
            if dates:
                y, m, d = dates[-1]
                deadline = f"{int(y):04d}-{int(m):02d}-{int(d):02d}"
                break
    summary = " ".join(sentences(page)[:2])[:300]
    return {
        "is_opportunity": is_opp and bool(title),
        "title": title or "제목 없는 공고",
        "organizer": "",
        "category": category,
        "summary": summary or title,
        "eligibility": {"grades": [], "majors": [], "region": "", "team": None, "notes": ""},
        "benefits": "",
        "apply_start": None,
        "apply_deadline": deadline,
        "result_announce_on": None,
        "activity_start": None,
        "activity_end": None,
        "location": "",
        "is_online": None,
        "tags": skills_in(page)[:8],
    }


def reco_reason(variables: dict[str, Any]) -> dict[str, Any]:
    items = variables.get("ITEMS") or []
    opp = variables.get("OPPORTUNITY") or {}
    goal = variables.get("GOAL") or "진로"
    if items:
        first = items[0]
        return {
            "reason": f"{goal} 목표와 이어지는 공고다. '{first['title']}' 경험을 살릴 수 있다.",
            "reason_item_ids": [first["id"]],
        }
    return {
        "reason": f"{goal} 목표와 관심 분야에 맞는 '{opp.get('title', '')}' 공고다.",
        "reason_item_ids": [],
    }


HANDLERS["normalize_opportunity"] = normalize_opportunity
HANDLERS["reco_reason"] = reco_reason


def activity_summary(variables: dict[str, Any]) -> dict[str, Any]:
    """규칙 기반 활동 요약: 근거 인용을 날짜순으로 이어 붙인다(새 사실을 만들지 않는다)."""
    quotes = [str(q.get("quote", "")).strip().rstrip(".") for q in variables.get("QUOTES") or []]
    quotes = [q for q in quotes if q][:5]
    text = " ".join(f"{q}." for q in quotes)
    return {"summary": text, "role": None, "metrics": [], "skills": skills_in(" ".join(quotes))}


HANDLERS["activity_summary"] = activity_summary
