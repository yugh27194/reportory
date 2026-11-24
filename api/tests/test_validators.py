"""추출 검증기 단위 테스트(인계서 10.2절, 11.1절 완료 기준)."""

import uuid
from datetime import date

from app.llm.schemas import ExtractionResult
from app.llm.validators import (
    drop_unsupported_sentences,
    numbers_supported,
    quote_in_source,
    validate_extraction,
)
from app.services.skills import normalize_skill

ENTRY = "오늘 OO 해커톤에서 팀원 3명과 FastAPI로 백엔드를 맡았다. 결과 발표에서 우수상을 받았다."
D = date(2026, 11, 18)


def cand(**kw):
    base = {
        "action": "create",
        "type": "project",
        "title": "OO 해커톤",
        "quote": "팀원 3명과 FastAPI로 백엔드를 맡았다",
        "confidence": 0.9,
    }
    return {**base, **kw}


def run(items=None, followups=None, updates=None, known=(), apps=(), relevant=True):
    raw = ExtractionResult.model_validate(
        {
            "is_relevant": relevant,
            "entry_summary": "해커톤에 참가했다.",
            "items": items or [],
            "followups": followups or [],
            "application_updates": updates or [],
        }
    )
    return validate_extraction(raw, ENTRY, D, set(known), set(apps))


def test_quote_must_be_substring_with_whitespace_normalized():
    assert quote_in_source("팀원 3명과   FastAPI로\n백엔드를", ENTRY)
    assert not quote_in_source("팀원 4명과 FastAPI로", ENTRY)
    assert not quote_in_source("   ", ENTRY)


def test_candidate_with_invented_quote_is_dropped():
    result, report, _ = run([cand(quote="팀원 5명과 Django로 개발했다")])
    assert result.items == []
    assert report.dropped_candidates == 1


def test_golden_hackathon_two_creates_keep_only_supported_numbers():
    result, report, _ = run(
        [
            cand(
                role="백엔드",
                skills=["FastAPI"],
                details={"team_size": 3, "demo_url": None},
                metrics=[{"name": "참가 팀", "value": "120팀"}],
            ),
            cand(
                type="award",
                title="OO 해커톤 우수상",
                quote="결과 발표에서 우수상을 받았다",
                details={"rank": "우수상", "host": "OO", "issuer": "x"},
            ),
        ]
    )
    assert [c.type for c in result.items] == ["project", "award"]
    project, award = result.items
    assert project.details == {"team_size": 3}
    assert project.metrics == []  # 120은 원문에 없다
    assert award.details == {"rank": "우수상", "host": "OO"}  # award에 issuer 키는 없다
    assert report.dropped_values == 1


def test_low_confidence_is_kept_but_unknown_target_is_dropped():
    known = uuid.uuid4()
    result, report, _ = run(
        [
            cand(confidence=0.4),
            cand(action="update", target_item_id=str(uuid.uuid4())),
            cand(action="link", target_item_id=str(known)),
        ],
        known=[known],
    )
    # 신뢰도가 낮아도 버리지 않는다. 모르는 항목 id는 버린다.
    assert len(result.items) == 2 and result.items[1].target_item_id == known
    assert report.dropped_candidates == 1


def test_dates_out_of_range_or_future_end_are_cleared():
    result, _, _ = run([cand(start_date="2001-01-01", end_date="2027-01-01", is_ongoing=False)])
    assert result.items[0].start_date is None
    assert result.items[0].end_date is None
    result, _, _ = run([cand(end_date="2027-01-01", is_ongoing=True)])
    assert result.items[0].end_date == date(2027, 1, 1)


def test_summary_sentences_with_invented_numbers_are_removed():
    text, dropped = drop_unsupported_sentences("백엔드를 맡았다. 정확도를 95%까지 올렸다.", ENTRY)
    assert text == "백엔드를 맡았다."
    assert dropped == 1
    assert numbers_supported("팀원 3명", ENTRY)
    assert not numbers_supported("팀원 4명", ENTRY)


def test_followup_targets_are_remapped_after_drops():
    known = uuid.uuid4()
    result, _, index_map = run(
        [cand(quote="없는 문장"), cand()],
        followups=[
            {"target": "candidate:1", "question": "맡은 역할은?", "reason": "역할"},
            {"target": "candidate:0", "question": "버려진 후보", "reason": "x"},
            {"target": f"item:{known}", "question": "수치는?", "reason": "수치"},
        ],
        known=[known],
    )
    assert index_map == {1: 0}
    assert [f.target for f in result.followups] == ["candidate:0", f"item:{known}"]


def test_application_updates_need_known_application_and_quote():
    app_id = uuid.uuid4()
    result, report, _ = run(
        updates=[
            {
                "application_id": str(app_id),
                "to_status": "accepted",
                "quote": "우수상을 받았다",
                "confidence": 0.9,
            },
            {
                "application_id": str(uuid.uuid4()),
                "to_status": "accepted",
                "quote": "우수상을 받았다",
                "confidence": 0.9,
            },
        ],
        apps=[app_id],
    )
    assert [u.application_id for u in result.application_updates] == [app_id]
    assert report.dropped_application_updates == 1


def test_irrelevant_entry_produces_nothing():
    result, _, _ = run([cand()], relevant=False)
    assert result.items == [] and result.followups == []


def test_skill_normalization():
    assert normalize_skill("PyTorch") == normalize_skill("pytorch") == normalize_skill("Py Torch")
    assert normalize_skill("Py-Torch") == "pytorch"
    assert normalize_skill("Node.js") == normalize_skill("nodejs")
    assert len({normalize_skill("C"), normalize_skill("C++"), normalize_skill("C#")}) == 3
