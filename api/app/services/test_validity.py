"""어학 시험별 유효기간(인계서 10.10절 5번). 표에 없는 시험은 유효기간을 채우지 않는다."""

from datetime import date

from app.services.skills import normalize_skill

# 정규화한 시험 이름에 들어 있는 표현 → 유효기간(년). 긴 이름부터 맞춘다.
VALIDITY_YEARS: list[tuple[str, int]] = [
    ("toeicspeaking", 2),
    ("토익스피킹", 2),
    ("toeic", 2),
    ("토익", 2),
    ("toefl", 2),
    ("토플", 2),
    ("teps", 2),
    ("텝스", 2),
    ("opic", 2),
    ("오픽", 2),
    ("ielts", 2),
    ("아이엘츠", 2),
]


def validity_years(test_name: str | None) -> int | None:
    if not test_name:
        return None
    norm = normalize_skill(test_name)
    return next((years for key, years in VALIDITY_YEARS if key in norm), None)


def estimate_expiry(test_name: str | None, issued_on: date | None) -> date | None:
    years = validity_years(test_name)
    if years is None or issued_on is None:
        return None
    try:
        return issued_on.replace(year=issued_on.year + years)
    except ValueError:
        return issued_on.replace(year=issued_on.year + years, day=28)
