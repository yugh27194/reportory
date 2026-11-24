"""성장 나무 단계, 레이더 목표 기준선, 일기 책장 달력."""

from app.services.growth import resolve_target, stage_for
from tests.test_flow import hackathon_extraction, pending, write_and_extract


def test_stage_thresholds():
    assert stage_for(0)["key"] == "pot"
    assert stage_for(1)["key"] == "sprout"
    assert stage_for(10)["key"] == "seedling"
    s = stage_for(45)
    assert s["key"] == "sapling" and s["next_at"] == 60 and 0 < s["progress"] < 1
    assert stage_for(500)["key"] == "tree" and stage_for(500)["next_at"] is None


def test_resolve_target_defaults():
    assert resolve_target(None, "grad_school")["preset"] == "grad_school"
    t = resolve_target({"preset": "custom", "values": {"award": 5}}, "employment")
    assert t["preset"] == "custom" and t["values"]["award"] == 5
    assert set(t["values"]) == {
        "experience",
        "project",
        "activity",
        "award",
        "certification",
        "language_test",
        "publication",
    }


async def test_growth_radar_and_calendar(make_user, mock_llm):
    mock_llm.on("extract_entry", hackathon_extraction)
    user = await make_user()
    g = (await user.client.get("/me/growth")).json()
    assert g["stage"]["key"] == "pot" and g["radar"]["target"]["preset"] == "dev_job"

    await write_and_extract(user, entry_date="2026-03-14")
    for p in await pending(user):
        await user.client.post(f"/proposals/{p['id']}/accept")
    g = (await user.client.get("/me/growth")).json()
    assert g["stage"]["level"] >= 1 and g["items_total"] >= 1
    assert sum(g["radar"]["values"].values()) >= 1

    r = await user.client.put(
        "/me/spec-target", json={"preset": "custom", "values": {"project": 7, "bogus": 3}}
    )
    assert r.status_code == 200 and r.json()["values"]["project"] == 7
    assert "bogus" not in r.json()["values"]
    g = (await user.client.get("/me/growth")).json()
    assert g["radar"]["target"]["values"]["project"] == 7

    cal = (await user.client.get("/journal/calendar?year=2026")).json()
    assert 2026 in cal["years"]
    day = cal["days"]["2026-03-14"]
    assert day["entries"] == 1 and day["items"] >= 1 and "body" not in day


async def test_calendar_is_per_user(make_user, mock_llm):
    mock_llm.on("extract_entry", hackathon_extraction)
    a = await make_user()
    b = await make_user()
    await write_and_extract(a, entry_date="2026-05-02")
    cal = (await b.client.get("/journal/calendar?year=2026")).json()
    assert cal["days"] == {}


def test_streak_counts_back_from_today_or_yesterday():
    from datetime import date, timedelta

    from app.routers.me import streak_of

    t = date(2026, 11, 25)
    d = lambda n: t - timedelta(days=n)  # noqa: E731
    assert streak_of([], t) == 0
    assert streak_of([d(0), d(1), d(2), d(4)], t) == 3
    assert streak_of([d(1), d(2)], t) == 2  # 오늘 아직 안 썼어도 어제까지 이어지면 유지
    assert streak_of([d(2), d(3)], t) == 0
