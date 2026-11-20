"""일기 → 추출 → 검토 큐 → 승인 → 포트폴리오·공개 프로필 통합 테스트(인계서 11.1·11.2절, 16장)."""

import json

from tests.conftest import drain_jobs

HACKATHON = (
    "오늘 OO 해커톤에서 팀원 3명과 FastAPI로 백엔드를 맡았다. 결과 발표에서 우수상을 받았다."
)


def hackathon_extraction(variables):
    return {
        "is_relevant": True,
        "entry_summary": "OO 해커톤에서 백엔드를 맡고 우수상을 받았다.",
        "items": [
            {
                "action": "create",
                "type": "project",
                "title": "OO 해커톤 프로젝트",
                "role": "백엔드",
                "summary_append": "팀원 3명과 FastAPI로 백엔드를 맡았다.",
                "skills": ["FastAPI"],
                "details": {"team_size": 3},
                "quote": "팀원 3명과 FastAPI로 백엔드를 맡았다",
                "confidence": 0.9,
            },
            {
                "action": "create",
                "type": "award",
                "title": "OO 해커톤 우수상",
                "details": {"rank": "우수상"},
                "quote": "결과 발표에서 우수상을 받았다",
                "confidence": 0.85,
            },
            {
                "action": "create",
                "type": "award",
                "title": "지어낸 상",
                "quote": "대상을 받았다",
                "confidence": 0.95,
            },
        ],
        "followups": [
            {
                "target": "candidate:0",
                "question": "프로젝트 결과물 링크가 있나요?",
                "reason": "링크가 없다",
            }
        ],
    }


async def write_and_extract(user, body=HACKATHON, entry_date="2026-11-18"):
    r = await user.client.post("/entries", json={"entry_date": entry_date, "body": body})
    assert r.status_code == 202, r.text
    data = r.json()
    await drain_jobs()
    return data


async def pending(user):
    r = await user.client.get("/proposals")
    assert r.status_code == 200
    return r.json()["proposals"]


async def test_auth_required_and_error_format(anon, make_user):
    r = await anon.get("/me")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthorized"
    user = await make_user()
    r = await user.client.get("/me")
    assert r.status_code == 200
    assert r.json()["user_id"] == str(user.id)


async def test_entry_without_consent_does_not_extract(make_user, mock_llm):
    user = await make_user(consent=False)
    data = await write_and_extract(user)
    assert data["job_id"] is None
    assert mock_llm.calls == []
    r = await user.client.post(f"/entries/{data['entry']['id']}/reextract")
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "consent_required"


async def test_core_loop(make_user, mock_llm, pg):
    mock_llm.on("extract_entry", hackathon_extraction)
    user = await make_user()
    data = await write_and_extract(user)

    job = (await user.client.get(f"/jobs/{data['job_id']}")).json()
    assert job["status"] == "succeeded"
    assert job["result"]["proposals"] == 2  # 인용이 원문에 없는 '지어낸 상'은 버린다
    assert job["result"]["dropped_candidates"] == 1
    assert await pg.fetchval("select count(*) from items where title = '지어낸 상'") == 0
    assert await pg.fetchval("select count(*) from llm_calls where user_id = $1", user.id) == 1

    proposals = await pending(user)
    assert {p["kind"] for p in proposals} == {"create_item"}
    assert all(p["quote"] in HACKATHON for p in proposals)
    followups = (await user.client.get("/followups")).json()["followups"]
    assert len(followups) == 1

    # 승인 전에는 포트폴리오에 나오지 않는다.
    assert (await user.client.get("/items")).json()["items"] == []

    project = next(p for p in proposals if p["item"]["type"] == "project")
    r = await user.client.post(f"/proposals/{project['id']}/accept")
    assert r.status_code == 200, r.text
    items = (await user.client.get("/items")).json()["items"]
    assert [i["title"] for i in items] == ["OO 해커톤 프로젝트"]
    assert items[0]["skills"] == ["FastAPI"]
    assert items[0]["details"] == {"team_size": 3}

    detail = (await user.client.get(f"/items/{items[0]['id']}")).json()
    assert detail["sources"][0]["quote"] == "팀원 3명과 FastAPI로 백엔드를 맡았다"

    award = next(p for p in proposals if p["item"]["type"] == "award")
    r = await user.client.post(f"/proposals/{award['id']}/reject")
    assert r.status_code == 200
    assert (
        await pg.fetchval(
            "select status from items where id = $1", __import__("uuid").UUID(award["item_id"])
        )
        == "rejected"
    )
    r = await user.client.post(f"/proposals/{award['id']}/accept")
    assert r.status_code == 409


async def test_edit_then_accept_revalidates(make_user, mock_llm):
    mock_llm.on("extract_entry", hackathon_extraction)
    user = await make_user()
    await write_and_extract(user)
    p = next(p for p in await pending(user) if p["item"]["type"] == "project")
    r = await user.client.post(
        f"/proposals/{p['id']}/accept", json={"edited_payload": {"start_date": "1990-01-01"}}
    )
    assert r.status_code == 422
    r = await user.client.post(
        f"/proposals/{p['id']}/accept",
        json={"edited_payload": {"title": "해커톤 백엔드", "skills": ["FastAPI", "PostgreSQL"]}},
    )
    assert r.status_code == 200
    item = (await user.client.get("/items")).json()["items"][0]
    assert item["title"] == "해커톤 백엔드"
    assert item["skills"] == ["FastAPI", "PostgreSQL"]


async def test_bulk_accept_requires_high_confidence(make_user, mock_llm):
    mock_llm.on("extract_entry", hackathon_extraction)
    user = await make_user()
    await write_and_extract(user)
    ids = [p["id"] for p in await pending(user)]
    r = await user.client.post("/proposals/bulk-accept", json={"ids": ids})
    assert r.status_code == 200
    assert len((await user.client.get("/items")).json()["items"]) == 2


async def test_bulk_accept_rejects_low_confidence(make_user, mock_llm):
    def low(variables):
        data = hackathon_extraction(variables)
        data["items"][1]["confidence"] = 0.6
        return data

    mock_llm.on("extract_entry", low)
    user = await make_user()
    await write_and_extract(user)
    ids = [p["id"] for p in await pending(user)]
    r = await user.client.post("/proposals/bulk-accept", json={"ids": ids})
    assert r.status_code == 422
    assert (await user.client.get("/items")).json()["items"] == []


async def test_reextract_rejects_pending_and_keeps_approved(make_user, mock_llm, pg):
    mock_llm.on("extract_entry", hackathon_extraction)
    user = await make_user()
    data = await write_and_extract(user)
    first = await pending(user)
    project = next(p for p in first if p["item"]["type"] == "project")
    await user.client.post(f"/proposals/{project['id']}/accept")

    r = await user.client.post(f"/entries/{data['entry']['id']}/reextract")
    assert r.status_code == 202
    await drain_jobs()
    award = next(p for p in first if p["item"]["type"] == "award")
    status = await pg.fetchval(
        "select status from proposals where id = $1", __import__("uuid").UUID(award["id"])
    )
    assert status == "rejected"
    approved = (await user.client.get("/items")).json()["items"]
    assert [i["title"] for i in approved] == ["OO 해커톤 프로젝트"]
    # 재추출에서 같은 제목 프로젝트는 중복 의심으로 표시된다.
    again = await pending(user)
    dup = next(p for p in again if p["item"]["type"] == "project")
    assert dup["possible_duplicate_of"] == approved[0]["id"]


async def test_update_and_followup_answer(make_user, mock_llm):
    mock_llm.on("extract_entry", hackathon_extraction)
    user = await make_user()
    await write_and_extract(user)
    project = next(p for p in await pending(user) if p["item"]["type"] == "project")
    await user.client.post(f"/proposals/{project['id']}/accept")
    item_id = project["item_id"]

    def second(variables):
        known = (
            json.loads(variables["KNOWN_ITEMS"])
            if isinstance(variables["KNOWN_ITEMS"], str)
            else variables["KNOWN_ITEMS"]
        )
        assert any(k["id"] == item_id for k in known)
        return {
            "is_relevant": True,
            "entry_summary": "정확도가 올랐다.",
            "items": [
                {
                    "action": "update",
                    "target_item_id": item_id,
                    "type": "project",
                    "title": "OO 해커톤 프로젝트",
                    "summary_append": "검증 정확도를 0.78까지 올렸다.",
                    "metrics": [
                        {"name": "검증 정확도", "value": "0.78"},
                        {"name": "속도", "value": "2배"},
                    ],
                    "quote": "검증 정확도가 0.71에서 0.78로 올랐다",
                    "confidence": 0.9,
                }
            ],
        }

    mock_llm.on("extract_entry", second)
    await write_and_extract(
        user, "모델 다시 돌림. 검증 정확도가 0.71에서 0.78로 올랐다.", "2026-11-19"
    )
    upd = next(p for p in await pending(user) if p["kind"] == "update_item")
    assert upd["payload"]["patch"]["metrics_add"] == [
        {"name": "검증 정확도", "value": "0.78", "unit": None}
    ]
    assert (await user.client.post(f"/proposals/{upd['id']}/accept")).status_code == 200

    fq = (await user.client.get("/followups")).json()["followups"][0]
    mock_llm.on(
        "answer_followup",
        lambda v: {
            "action": "update",
            "type": "project",
            "title": "x",
            "details": {"repo_url": "https://github.com/me/hack"},
            "summary_append": "결과물은 GitHub에 공개했다.",
            "quote": "https://github.com/me/hack",
            "confidence": 0.9,
        },
    )
    r = await user.client.post(
        f"/followups/{fq['id']}/answer", json={"answer": "https://github.com/me/hack 에 올렸어요"}
    )
    assert r.status_code == 202
    await drain_jobs()
    ans = next(p for p in await pending(user) if p["kind"] == "update_item")
    assert ans["payload"]["followup_id"] == fq["id"]
    await user.client.post(f"/proposals/{ans['id']}/accept")

    detail = (await user.client.get(f"/items/{item_id}")).json()
    assert detail["metrics"] == [{"name": "검증 정확도", "value": "0.78", "unit": None}]
    assert detail["details"]["repo_url"] == "https://github.com/me/hack"
    assert "0.78" in detail["summary"] and "GitHub" in detail["summary"]
    assert any(s["followup_id"] == fq["id"] for s in detail["sources"])
    assert len(detail["sources"]) == 3


async def test_manual_item_and_merge(make_user):
    user = await make_user()
    a = (
        await user.client.post(
            "/items", json={"type": "activity", "title": "멘토링", "skills": ["Python"]}
        )
    ).json()
    b = (
        await user.client.post(
            "/items", json={"type": "activity", "title": "멘토링 2기", "skills": ["python", "Git"]}
        )
    ).json()
    assert a["status"] == "approved" and a["sources"][0]["import_id"]
    r = await user.client.post(
        "/items/merge", json={"keep_item_id": a["id"], "merge_item_ids": [b["id"]]}
    )
    assert r.status_code == 200
    merged = r.json()
    assert merged["skills"] == ["Git", "Python"]
    assert len(merged["sources"]) == 2
    archived = (await user.client.get("/items", params={"status": "archived"})).json()["items"]
    assert [i["id"] for i in archived] == [b["id"]]


async def test_other_users_resources_are_404(make_user, mock_llm):
    mock_llm.on("extract_entry", hackathon_extraction)
    alice, bob = await make_user(), await make_user()
    data = await write_and_extract(alice)
    item = (await alice.client.post("/items", json={"type": "award", "title": "상"})).json()
    proposal = (await pending(alice))[0]
    for path in (
        f"/items/{item['id']}",
        f"/entries/{data['entry']['id']}",
        f"/jobs/{data['job_id']}",
    ):
        r = await bob.client.get(path)
        assert r.status_code == 404, path
        assert r.json()["error"]["code"] == "not_found"
    assert (await bob.client.patch(f"/items/{item['id']}", json={"title": "x"})).status_code == 404
    assert (await bob.client.post(f"/proposals/{proposal['id']}/accept")).status_code == 404
    r = await bob.client.post(
        "/items/merge", json={"keep_item_id": item["id"], "merge_item_ids": [item["id"]]}
    )
    assert r.status_code in (404, 422)


async def test_public_profile(make_user, anon):
    user = await make_user()
    assert (await anon.get("/public/nobody")).status_code == 404
    r = await user.client.patch("/me/profile", json={"public_profile_enabled": True})
    assert r.status_code == 422
    handle = f"u{user.id.hex[:10]}"
    r = await user.client.patch("/me/profile", json={"handle": handle, "display_name": "홍길동"})
    assert r.status_code == 200
    assert (await anon.get(f"/public/{handle}")).status_code == 404  # 아직 꺼져 있다

    await user.client.post(
        "/items", json={"type": "project", "title": "공개 프로젝트", "visibility": "public"}
    )
    await user.client.post("/items", json={"type": "project", "title": "비공개 프로젝트"})
    await user.client.patch("/me/profile", json={"public_profile_enabled": True})
    r = await anon.get(f"/public/{handle}")
    assert r.status_code == 200
    body = r.json()
    assert body["profile"]["display_name"] == "홍길동"
    assert [i["title"] for i in body["items"]] == ["공개 프로젝트"]
    assert "user_id" not in json.dumps(body)


async def test_delete_entry_keeps_approved_items(make_user, mock_llm):
    mock_llm.on("extract_entry", hackathon_extraction)
    user = await make_user()
    data = await write_and_extract(user)
    project = next(p for p in await pending(user) if p["item"]["type"] == "project")
    await user.client.post(f"/proposals/{project['id']}/accept")
    r = await user.client.delete(f"/entries/{data['entry']['id']}")
    assert r.status_code == 204
    assert await pending(user) == []
    items = (await user.client.get("/items")).json()["items"]
    assert [i["title"] for i in items] == ["OO 해커톤 프로젝트"]
    assert items[0]["source_count"] == 0


async def test_merge_duplicate_proposal_into_existing_item(make_user, mock_llm, pg):
    """검토 화면의 '기존 항목에 합치기': 제안 항목을 승인된 항목에 합치면 제안은 거절 처리된다."""
    mock_llm.on("extract_entry", hackathon_extraction)
    user = await make_user()
    existing = (
        await user.client.post("/items", json={"type": "project", "title": "OO 해커톤 프로젝트"})
    ).json()
    await write_and_extract(user)
    dup = next(p for p in await pending(user) if p["item"]["type"] == "project")
    assert dup["possible_duplicate_of"] == existing["id"]

    r = await user.client.post(
        "/items/merge", json={"keep_item_id": existing["id"], "merge_item_ids": [dup["item_id"]]}
    )
    assert r.status_code == 200
    merged = r.json()
    assert merged["skills"] == ["FastAPI"]
    assert any(s["entry_id"] for s in merged["sources"])
    status = await pg.fetchval(
        "select status from proposals where id = $1", __import__("uuid").UUID(dup["id"])
    )
    assert status == "rejected"
    assert all(p["id"] != dup["id"] for p in await pending(user))
