"""LLM 출력 스키마(인계서 10장). 모든 LLM 출력은 이 모델로 검증한다."""

from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

ItemType = Literal[
    "education",
    "experience",
    "project",
    "activity",
    "award",
    "certification",
    "language_test",
    "publication",
]

# 유형별로 허용하는 details 키(10.2절). 정해진 키 외의 값은 버린다.
DETAILS_KEYS: dict[str, tuple[str, ...]] = {
    "award": ("rank", "competition", "host"),
    "certification": ("issuer", "cert_number_last4"),
    "language_test": ("test", "score", "level", "test_date", "valid_until"),
    "project": ("team_size", "repo_url", "demo_url"),
    "experience": ("employment_type", "lab_or_team"),
    "publication": ("venue", "authors", "status", "doi"),
    "education": ("degree", "major", "gpa"),
    "activity": (),
}


class Metric(BaseModel):
    name: str
    value: str  # 원문 그대로: "15%", "0.82", "3위"
    unit: str | None = None


class ItemCandidate(BaseModel):
    action: Literal["create", "update", "link"]
    target_item_id: UUID | None = None  # update·link일 때 필수
    type: ItemType
    title: str
    organization: str | None = None
    role: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    is_ongoing: bool | None = None
    summary_append: str = ""
    skills: list[str] = []
    metrics: list[Metric] = []
    details: dict = {}
    quote: str
    confidence: float = Field(ge=0, le=1)


class ApplicationUpdate(BaseModel):
    application_id: UUID
    to_status: Literal["accepted", "rejected", "withdrawn", "active", "completed"]
    result_date: date | None = None
    quote: str
    confidence: float = Field(ge=0, le=1)


class FollowupQuestion(BaseModel):
    target: str  # "item:<uuid>" 또는 "candidate:<index>"
    question: str
    reason: str


class ExtractionResult(BaseModel):
    is_relevant: bool
    entry_summary: str
    items: list[ItemCandidate] = []
    application_updates: list[ApplicationUpdate] = []
    followups: list[FollowupQuestion] = Field(default_factory=list, max_length=3)


class ActivitySummary(BaseModel):
    summary: str
    role: str | None = None
    metrics: list[Metric] = []
    skills: list[str] = []


class EvidenceExtract(BaseModel):
    """증빙 분류와 추출(10.10절)."""

    kind: Literal[
        "language_score", "certificate", "award_certificate", "completion_certificate", "other"
    ]
    title: str | None = None  # 시험명, 자격명, 대회명, 과정명
    issuer: str | None = None
    issued_on: date | None = None
    expires_on: date | None = None
    score: str | None = None  # 어학 점수·등급
    award_rank: str | None = None
    confidence: float = Field(ge=0, le=1)


class DocLine(BaseModel):
    text: str
    item_id: UUID


class DocSection(BaseModel):
    item_id: UUID
    heading: str | None = None
    lines: list[DocLine]


class RewriteResult(BaseModel):
    """문서 문장 변환(10.8절)."""

    summary: str | None = None  # Resume 상단 요약
    sections: list[DocSection]
