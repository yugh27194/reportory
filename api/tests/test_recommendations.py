"""활동 추천(인계서 11.4절, 10.6절, 10.7절)과 지원 상태 전이(8.3절, 11.3절)."""

from datetime import date, timedelta

import httpx
import pytest

from app.crawler import fetch as F
from app.llm.schemas import OpportunityExtract
from app.services import recommend as R
from app.services.opportunities import clean_opportunity
from tests.conftest import CRON_SECRET, drain_jobs
from tests.test_flow import hackathon_extraction, pending, write_and_extract

CRON = {"X-Cron-Secret": CRON_SECRET}
TODAY = date.today()
SOON = TODAY + timedelta(days=10)
LATER = TODAY + timedelta(days=40)


def page_html(title: str, deadline: date, extra: str = "") -> str:
    body = (
        f"<p>{title} 참가자를 모집한다. 주최: 한국데이터진흥원. 대학생이면 누구나 지원할 수 있다.</p>"
        f"<p>접수 마감: {deadline.year}.{deadline.month}.{deadline.day}</p>"
        f"<p>총 상금 500만원. AI, 데이터 분석 분야 팀(2~4명) 참가.</p>{extra}"
    )
    return f"<html><head><title>{title}</title></head><body>{body * 3}</body></html>"


PAGES = {
    "https://contest.example.org/robots.txt": (
        200,
        "text/plain",
        "User-agent: *\nDisallow: /private\n",
    ),
    "https://contest.example.org/ai": (200, "text/html", page_html("AI 데이터 해커톤", SOON)),
    "https://contest.example.org/design": (200, "text/html", page_html("디자인 공모전", LATER)),
    "https://contest.example.org/private/x": (200, "text/html", page_html("비공개", LATER)),
    "https://contest.example.org/news": (
        200,
        "text/html",
        "<html><title>뉴스</title>" + "기사 " * 200,
    ),
}


def transport_handler(request: httpx.Request) -> httpx.Response:
    url = str(request.url)
    if url not in PAGES:
        return httpx.Response(404)
    status, ctype, body = PAGES[url]
    return httpx.Response(status, headers={"content-type": f"{ctype}; charset=utf-8"}, text=body)


async def public_resolver(host: str) -> list[str]:
    return ["10.0.0.5"] if host == "intranet.example.org" else ["93.184.216.34"]


@pytest.fixture(autouse=True)
def crawler_hooks():
    F.set_test_hooks(resolver=public_resolver, transport=httpx.MockTransport(transport_handler))
    yield
    F.set_test_hooks()


def normalize(variables):
    title = variables["PAGE_TITLE"]
    page = variables["PAGE"]
    if title == "뉴스":
        return {
            "is_opportunity": False,
            "title": "뉴스",
            "category": "other",
            "summary": "",
            "eligibility": {},
        }
    deadline = SOON if "해커톤" in title else LATER
    return {
        "is_opportunity": True,
        "title": title,
        "organizer": "한국데이터진흥원",
        "category": "hackathon" if "해커톤" in title else "contest",
        "summary": f"{title}이다. 상금은 500만원이다. 참가비는 999만원이다.",
        "eligibility": {"grades": [3, 4] if "디자인" in title else [], "majors": []},
        "benefits": "총 상금 500만원",
        "apply_deadline": deadline.isoformat(),
        "result_announce_on": (TODAY + timedelta(days=77)).isoformat(),  # 본문에 없는 날짜
        "tags": ["AI", "데이터 분석"] if "AI" in page[:100] or "해커톤" in title else ["디자인"],
    }


# ---------- 단위 ----------


async def test_check_url_blocks_internal_and_odd_urls():
    for bad in [
        "ftp://contest.example.org/a",
        "https://intranet.example.org/a",
        "https://user:pw@contest.example.org/a",
        "https://contest.example.org:8443/a",
    ]:
        with pytest.raises(F.FetchError):
            await F.check_url(bad)
    assert await F.check_url("https://contest.example.org/ai")


async def test_fetch_respects_robots_and_extracts_text():
    page = await F.fetch_page("https://contest.example.org/ai")
    assert "참가자를 모집한다" in page.text and page.title == "AI 데이터 해커톤"
    with pytest.raises(F.FetchError, match="robots"):
        await F.fetch_page("https://contest.example.org/private/x")


def test_clean_opportunity_drops_unsupported_facts():
    text = page_html("AI 데이터 해커톤", SOON)
    ext = OpportunityExtract.model_validate(
        normalize({"PAGE_TITLE": "AI 데이터 해커톤", "PAGE": text})
    )
    data = clean_opportunity(ext, text, TODAY)
    assert data["apply_deadline"] == SOON
    assert data["result_announce_on"] is None  # 본문에 없는 날짜는 버린다
    assert "999" not in data["summary"] and "500" in data["summary"]
    assert data["organizer"] == "한국데이터진흥원"
    ext2 = ext.model_copy(update={"organizer": "지어낸 재단", "is_opportunity": True})
    assert clean_opportunity(ext2, text, TODAY)["organizer"] is None
    assert clean_opportunity(ext.model_copy(update={"is_opportunity": False}), text, TODAY) is None


def ctx(**kw) -> R.UserContext:
    base = dict(
        goal="employment",
        grade=3,
        major="컴퓨터공학",
        interests=["AI"],
        target_roles=[],
        skills=set(),
        items=[],
    )
    return R.UserContext(**{**base, **kw})


def test_pref_penalty_after_two_rejections():
    c = ctx(outcomes={"contest": {"rejected": 2}})
    assert R.pref_score(c, "contest") == pytest.approx(-0.3)
    c2 = ctx(outcomes={"contest": {"rejected": 2, "accepted": 1}})
    assert R.pref_score(c2, "contest") == 0
    c3 = ctx(pref_counts={"hackathon": {"interested": 3}})
    assert R.pref_score(c3, "hackathon") == pytest.approx(0.5)


def test_gap_rules_and_diversity():
    assert R.gap_score(ctx(), {"category": "internship", "tags": []}) == 1
    exp = ctx(
        items=[
            {"id": 1, "type": "experience", "title": "OO 인턴", "summary": "", "embedding": None}
        ]
    )
    assert R.gap_score(exp, {"category": "internship", "tags": []}) == 0
    grad = ctx(goal="grad_school")
    assert R.gap_score(grad, {"category": "research_internship", "tags": []}) == 1
    ranked = [{"category": "contest", "id": i} for i in range(6)] + [
        {"category": "hackathon", "id": 9}
    ]
    top = R.diversify(ranked)[:4]
    assert [r["category"] for r in top].count("contest") == 3 and top[3]["category"] == "hackathon"


def test_eligibility_by_grade_and_major():
    assert not R.eligible({"eligibility": {"grades": [3, 4]}}, 1, None)
    assert R.eligible({"eligibility": {"grades": [3, 4]}}, 3, None)
    assert R.eligible({"eligibility": {"grades": [3]}}, None, None)  # 학년을 모르면 막지 않는다
    assert not R.eligible({"eligibility": {"majors": ["디자인"]}}, 3, "컴퓨터공학")


# ---------- 통합 ----------


async def collect(anon, mock_llm, pg):
    await pg.execute("delete from opportunities where created_by is null")
    mock_llm.on(
        "web_search",
        lambda v: [
            {"url": "https://contest.example.org/ai", "title": "AI"},
            {"url": "https://contest.example.org/design", "title": "디자인"},
            {"url": "https://contest.example.org/news", "title": "뉴스"},
            {"url": "https://contest.example.org/private/x", "title": "막힘"},
        ],
    )
    mock_llm.on("normalize_opportunity", normalize)
    r = await anon.post("/internal/cron/collect_opportunities", headers=CRON)
    assert r.status_code == 200 and "job_id" in r.json()
    again = await anon.post("/internal/cron/collect_opportunities", headers=CRON)
    assert again.json()["skipped"] == "already_queued"
    await drain_jobs()
    return await pg.fetch(
        "select title, category, apply_deadline, is_active from opportunities where created_by is null order by title"
    )


async def test_collect_and_recommend_flow(make_user, mock_llm, anon, pg):
    rows = await collect(anon, mock_llm, pg)
    assert [r["title"] for r in rows] == [
        "AI 데이터 해커톤",
        "디자인 공모전",
    ]  # 뉴스·robots 차단 제외
    # 이미 지난 공고는 다음 수집 때 비활성화된다.
    await pg.execute(
        """insert into opportunities (source_url, title, category, apply_deadline)
           values ('https://old.example.org/x', '지난 공모전', 'contest', current_date - 1)"""
    )

    mock_llm.on("extract_entry", hackathon_extraction)
    user = await make_user()
    await user.client.patch(
        "/me/profile", json={"grade": 1, "goal": "employment", "interests": ["AI"]}
    )
    await write_and_extract(user)
    for p in await pending(user):
        await user.client.post(f"/proposals/{p['id']}/accept")
    approved = {i["id"] for i in (await user.client.get("/items?status=approved")).json()["items"]}

    def reason(v):
        ids = [i["id"] for i in v["ITEMS"]]
        return {
            "reason": "해커톤 경험을 살릴 수 있다. 상금 1억원도 있다.",
            "reason_item_ids": ids[:1] + ["00000000-0000-4000-8000-000000000000"],
        }

    mock_llm.on("reco_reason", reason)
    r = await anon.post("/internal/cron/score_recommendations", headers=CRON)
    assert r.json()["users"] >= 1
    await drain_jobs()
    recs = (await user.client.get("/recommendations")).json()["recommendations"]
    titles = [x["title"] for x in recs]
    assert "AI 데이터 해커톤" in titles
    assert "디자인 공모전" not in titles  # 3·4학년만 지원 가능
    assert "지난 공모전" not in titles
    hack = next(x for x in recs if x["title"] == "AI 데이터 해커톤")
    assert "1억" not in hack["reason"]  # 근거에 없는 숫자가 든 이유는 기본 문장으로 바뀐다
    assert all(i["id"] in approved for i in hack["reason_items"])
    assert hack["score_breakdown"]["urgency"] == 1

    # 관심 → 지원 항목 생성, 지원함 → applied
    fb = await user.client.post(
        f"/recommendations/{hack['id']}/feedback", json={"feedback": "interested"}
    )
    app = fb.json()["application"]
    assert app["status"] == "interested" and app["apply_deadline"] == SOON.isoformat()
    fb = await user.client.post(
        f"/recommendations/{hack['id']}/feedback", json={"feedback": "applied"}
    )
    app_id = fb.json()["application"]["id"]
    assert fb.json()["application"]["status"] == "applied"

    # 허용되지 않은 전이는 409
    bad = await user.client.post(
        f"/applications/{app_id}/transition", json={"to_status": "completed"}
    )
    assert bad.status_code == 409
    ok = await user.client.post(
        f"/applications/{app_id}/transition", json={"to_status": "accepted"}
    )
    assert ok.status_code == 200
    body = ok.json()
    assert body["status"] == "active" and body["item_id"]  # 활동 시작일이 없으면 바로 active
    item = (await user.client.get(f"/items/{body['item_id']}")).json()
    assert item["type"] == "project" and item["is_ongoing"] and item["status"] == "approved"
    done = await user.client.post(
        f"/applications/{app_id}/transition", json={"to_status": "completed"}
    )
    assert done.json()["status"] == "completed"
    item = (await user.client.get(f"/items/{body['item_id']}")).json()
    assert not item["is_ongoing"]
    detail = (await user.client.get(f"/applications/{app_id}")).json()
    assert [e["to_status"] for e in detail["events"]] == [
        "interested",
        "applied",
        "accepted",
        "active",
        "completed",
    ]

    # 숨김은 다시 추천되지 않는다.
    others = [x for x in recs if x["id"] != hack["id"]]
    for x in others:
        await user.client.post(
            f"/recommendations/{x['id']}/feedback", json={"feedback": "dismissed"}
        )
    await user.client.post("/recommendations/refresh")
    await drain_jobs()
    after = (await user.client.get("/recommendations")).json()["recommendations"]
    assert not any(x["id"] in {o["id"] for o in others} for x in after)


async def test_add_opportunity_by_url_is_private(make_user, mock_llm, anon, pg):
    mock_llm.on("normalize_opportunity", normalize)
    mock_llm.on("reco_reason", lambda v: {"reason": "관심 분야와 맞다.", "reason_item_ids": []})
    a = await make_user()
    b = await make_user()
    r = await a.client.post(
        "/opportunities/from-url", json={"url": "https://intranet.example.org/x"}
    )
    assert r.status_code == 422
    r = await a.client.post(
        "/opportunities/from-url", json={"url": "https://contest.example.org/design"}
    )
    assert r.status_code == 202
    await drain_jobs()
    job = (await a.client.get(f"/jobs/{r.json()['job_id']}")).json()
    assert job["status"] == "succeeded", job
    mine = await pg.fetch(
        "select created_by from opportunities where source_url = 'https://contest.example.org/design' and created_by is not null"
    )
    assert [m["created_by"] for m in mine] == [a.id]
    recs_a = (await a.client.get("/recommendations")).json()["recommendations"]
    assert any(x["title"] == "디자인 공모전" and x["added_by_me"] for x in recs_a)
    recs_b = (await b.client.get("/recommendations")).json()["recommendations"]
    assert not any(x["added_by_me"] for x in recs_b)
    # 공고가 아닌 페이지는 실패로 끝나고 이유를 남긴다.
    r = await a.client.post(
        "/opportunities/from-url", json={"url": "https://contest.example.org/news"}
    )
    await drain_jobs()
    job = (await a.client.get(f"/jobs/{r.json()['job_id']}")).json()
    assert job["status"] == "failed" and "공고" in job["last_error"]


async def test_auto_transitions_and_reminders(make_user, anon, pg):
    user = await make_user()
    app = (
        await user.client.post(
            "/applications",
            json={
                "title": "OO 서포터즈",
                "category": "external_activity",
                "apply_deadline": (TODAY - timedelta(days=14)).isoformat(),
            },
        )
    ).json()
    await user.client.post(f"/applications/{app['id']}/transition", json={"to_status": "applied"})
    r = await anon.post("/internal/cron/application_auto_transitions", headers=CRON)
    assert r.json()["changed"] >= 1
    assert (await user.client.get(f"/applications/{app['id']}")).json()[
        "status"
    ] == "awaiting_result"
    r = await anon.post("/internal/cron/result_reminders", headers=CRON)
    assert r.json()["result_reminders"] >= 1
    notes = (await user.client.get("/notifications")).json()["notifications"]
    assert any("결과가 나왔나요" in n["title"] for n in notes)
    r = await anon.post(
        "/internal/cron/result_reminders", headers=CRON
    )  # 같은 날 다시 불러도 한 번만
    notes2 = (await user.client.get("/notifications")).json()["notifications"]
    assert len(notes2) == len(notes)


async def test_diary_result_detection_accepts_application(make_user, mock_llm):
    """지원 applied 상태에서 본선 진출 일기 → accepted 제안 → 승인하면 항목 생성, 이벤트 source=diary."""
    user = await make_user()
    app = (
        await user.client.post(
            "/applications", json={"title": "OO 해커톤", "category": "hackathon"}
        )
    ).json()
    await user.client.post(f"/applications/{app['id']}/transition", json={"to_status": "applied"})

    def extraction(v):
        apps = v["OPEN_APPLICATIONS"]
        assert apps and apps[0]["id"] == app["id"]
        return {
            "is_relevant": True,
            "entry_summary": "OO 해커톤 본선 진출이 확정됐다.",
            "items": [],
            "application_updates": [
                {
                    "application_id": app["id"],
                    "to_status": "accepted",
                    "quote": "OO 해커톤 본선 진출 확정",
                    "confidence": 0.9,
                }
            ],
            "followups": [],
        }

    mock_llm.on("extract_entry", extraction)
    await write_and_extract(user, body="오늘 OO 해커톤 본선 진출 확정 소식을 들었다.")
    props = [p for p in await pending(user) if p["kind"] == "application_update"]
    assert len(props) == 1
    r = await user.client.post(f"/proposals/{props[0]['id']}/accept")
    assert r.status_code == 200, r.text
    detail = (await user.client.get(f"/applications/{app['id']}")).json()
    assert detail["status"] == "active" and detail["item_id"]
    assert any(e["to_status"] == "accepted" and e["source"] == "diary" for e in detail["events"])
