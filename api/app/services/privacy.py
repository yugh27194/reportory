"""식별번호 지우기(인계서 10.10절 6번, 14장). 주민등록번호, 여권번호, 긴 번호열은 저장하지 않는다."""

import re
from typing import Any

MASK = "[번호 삭제]"

_PATTERNS = [
    re.compile(r"\d{6}\s*-\s*[1-8]\d{6}"),  # 주민등록번호·외국인등록번호
    re.compile(r"\b[A-Z]{1,2}\d{7,8}\b"),  # 여권번호
    re.compile(r"(?<![\d-])(?:\d-?){9,}\d(?![\d-])"),  # 숫자 10자리 이상(수험번호, 자격증 번호 등)
]


def scrub(text: str | None) -> str | None:
    if not text:
        return text
    for pattern in _PATTERNS:
        text = pattern.sub(MASK, text)
    return text


def scrub_values(data: dict[str, Any]) -> dict[str, Any]:
    return {k: scrub(v) if isinstance(v, str) else v for k, v in data.items()}
