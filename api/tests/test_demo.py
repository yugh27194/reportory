"""키 없이 쓰는 데모 분석(LLM_PROVIDER=demo)."""

import pytest

from app.config import get_settings
from app.llm import client as llm_client
from app.llm.demo import answer_followup, extract_entry
from tests.conftest import drain_jobs
from tests.test_flow import pending

DIARY = "오늘 OO 해커톤에서 팀원 3명과 FastAPI로 백엔드를 맡았다. 결과 발표에서 우수상을 받았다."


def test_rules_find_project_and_award_with_verbatim_quotes():
    out = extract_entry({"ENTRY": DIARY, "KNOWN_ITEMS": []})
    assert [(i["action"], i["type"]) for i in out["items"]] == [
        ("create", "project"),
        ("create", "award"),
    ]
    assert all(i["quote"] in DIARY for i in out["items"])
    assert out["items"][0]["skills"] == ["FastAPI"]


def test_irrelevant_and_link_to_known_item():
    assert (
        extract_entry({"ENTRY": "비 와서 집에 있었다.", "KNOWN_ITEMS": []})["is_relevant"] is False
    )
    known = [{"id": "x", "type": "project", "title": "캡스톤 프로젝트"}]
    out = extract_entry({"ENTRY": "오늘도 캡스톤 프로젝트 회의를 했다.", "KNOWN_ITEMS": known})
    assert out["items"][0]["action"] == "link"


def test_followup_answer():
    out = answer_followup(
        {
            "ITEM": {"id": "x", "type": "project", "title": "t"},
            "ANSWER": "React로 화면을 만들었다. 그 외는 없다.",
        }
    )
    assert out["quote"] == "React로 화면을 만들었다."
    assert out["skills"] == ["React"]


@pytest.fixture
def demo_mode(monkeypatch):
    monkeypatch.setattr(get_settings(), "llm_provider", "demo")
    llm_client.set_llm(None)
    yield
    llm_client.set_llm(None)


async def test_demo_mode_end_to_end(make_user, demo_mode, pg):
    user = await make_user()
    r = await user.client.post("/entries", json={"entry_date": "2026-11-24", "body": DIARY})
    await drain_jobs()
    job = (await user.client.get(f"/jobs/{r.json()['job_id']}")).json()
    assert job["status"] == "succeeded" and job["result"]["proposals"] == 2
    proposals = await pending(user)
    assert all(p["confidence"] == pytest.approx(0.6) for p in proposals)
    row = await pg.fetchrow("select provider, model from llm_calls where user_id = $1", user.id)
    assert (row["provider"], row["model"]) == ("demo", "rule-based-demo")
