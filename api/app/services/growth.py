"""성장 나무와 스펙 레이더 계산.

- 나무 단계는 승인한 항목 수와 일기를 쓴 날 수로 정한다(점수 = 항목 x2 + 기록한 날).
- 레이더는 학력을 뺀 7개 축의 승인 항목 수를 목표 기준선과 견준다.
단계 기준과 기본 프리셋은 설정값으로 바꿀 수 있다(인계서 19장 방식).
"""

from app.config import get_settings

RADAR_AXES = [
    "experience",
    "project",
    "activity",
    "award",
    "certification",
    "language_test",
    "publication",
]

STAGES = [
    ("pot", "화분"),
    ("sprout", "새싹"),
    ("seedling", "어린 묘목"),
    ("sapling", "묘목"),
    ("tree", "올리브 나무"),
]

# 목표별 기준선(축마다 갖추면 좋은 항목 수). 국내 채용·진학 공고에서 흔히 요구하는 구성을
# 바탕으로 잡은 출발점이며, 사용자가 축마다 직접 고칠 수 있다.
PRESETS: dict[str, dict] = {
    "dev_job": {
        "label": "개발 직무 취업",
        "values": {
            "experience": 1,
            "project": 4,
            "activity": 2,
            "award": 1,
            "certification": 1,
            "language_test": 1,
            "publication": 0,
        },
    },
    "biz_job": {
        "label": "기획·마케팅 취업",
        "values": {
            "experience": 1,
            "project": 2,
            "activity": 3,
            "award": 2,
            "certification": 1,
            "language_test": 1,
            "publication": 0,
        },
    },
    "public_job": {
        "label": "공기업·공공기관",
        "values": {
            "experience": 1,
            "project": 1,
            "activity": 2,
            "award": 1,
            "certification": 3,
            "language_test": 1,
            "publication": 0,
        },
    },
    "grad_school": {
        "label": "대학원 진학",
        "values": {
            "experience": 1,
            "project": 2,
            "activity": 1,
            "award": 1,
            "certification": 0,
            "language_test": 1,
            "publication": 2,
        },
    },
}


def default_preset(goal: str | None) -> str:
    if goal == "grad_school":
        return "grad_school"
    return get_settings().spec_default_preset


def resolve_target(stored: dict | None, goal: str | None) -> dict:
    preset = (stored or {}).get("preset") or default_preset(goal)
    if preset not in PRESETS and preset != "custom":
        preset = default_preset(goal)
    base = PRESETS.get(preset, PRESETS[default_preset(goal)])["values"]
    values = {**base, **((stored or {}).get("values") or {})}
    return {"preset": preset, "values": {a: int(values.get(a, 0)) for a in RADAR_AXES}}


def thresholds() -> list[int]:
    raw = get_settings().growth_stage_thresholds
    return [int(x) for x in raw.split(",") if x.strip()]


def stage_for(score: int) -> dict:
    th = thresholds()
    level = sum(1 for t in th if score >= t)
    level = min(level, len(STAGES) - 1)
    key, label = STAGES[level]
    nxt = th[level] if level < len(th) else None
    prev = th[level - 1] if level > 0 else 0
    return {
        "level": level,
        "key": key,
        "label": label,
        "score": score,
        "next_at": nxt,
        "progress": 1.0 if nxt is None else round((score - prev) / max(1, nxt - prev), 3),
    }
