"""지원 항목 상태 전이 표(인계서 8.3절).

Phase 3에서 상태 전이 함수(`transition`)와 부수 효과를 이 모듈에 구현한다. Phase 1에서는
일기 추출이 허용된 전이만 제안으로 만들도록 표만 쓴다.
"""

ALLOWED_TRANSITIONS: dict[str | None, set[str]] = {
    None: {"interested"},
    "interested": {"applied", "withdrawn"},
    "applied": {"awaiting_result", "accepted", "rejected", "withdrawn"},
    "awaiting_result": {"accepted", "rejected", "withdrawn"},
    "accepted": {"active"},
    "active": {"completed"},
    "rejected": set(),
    "withdrawn": set(),
    "completed": set(),
}

OPEN_STATUSES = ("applied", "awaiting_result", "accepted", "active")


def is_allowed(from_status: str | None, to_status: str) -> bool:
    return to_status in ALLOWED_TRANSITIONS.get(from_status, set())
