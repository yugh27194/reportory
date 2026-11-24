"""추천 점수 가중치와 규칙 값(인계서 10.7절). 값만 바꿔 조정한다."""

W_SIM = 0.55
W_GAP = 0.20
W_PREF = 0.15
W_URGENCY = 0.10

URGENT_DAYS = 14  # 마감이 이 날수 안이면 urgency=1
RECENCY_HALF_LIFE_MONTHS = 6  # 항목 가중치 0.5^(경과 개월/6)
PREF_PRIOR = 3  # (관심 + 지원 − 숨김) / (전체 피드백 + 3)
REJECT_PENALTY = 0.3  # 같은 분류에서 불합격 2번 이상, 합격 0번이면 뺀다
REJECT_PENALTY_MIN_REJECTS = 2
DIVERSITY_TOP = 10  # 상위 10개 안에서
DIVERSITY_MAX_PER_CATEGORY = 3  # 같은 분류는 최대 3개

# 연구 경험으로 보는 표현(목표가 대학원일 때 gap 판단)
RESEARCH_HINTS = ("연구", "학부연구", "랩", "lab", "research")
