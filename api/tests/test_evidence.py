"""증빙 업로드·분류·연결(인계서 10.10절, 11.7절 완료 기준)."""

import uuid

from app.llm.demo import process_evidence as demo_evidence
from app.services.test_validity import estimate_expiry
from tests.conftest import drain_jobs
from tests.pdfgen import make_pdf
from tests.test_flow import pending

TOEIC_LINES = [
    "TOEIC Score Report",
    "Name: Hong Gildong  Registration No 123456789012",
    "Test Date 2026.05.12",
    "Listening 470 Reading 435 Total 905",
]


def toeic_extract(score="905"):
    def handler(v):
        assert "TOEIC" in v["TEXT"]
        return {
            "kind": "language_score",
            "title": "TOEIC",
            "issuer": "ETS",
            "issued_on": "2026-05-12",
            "score": score,
            "confidence": 0.9,
        }

    return handler


async def upload(user, data: bytes, name="toeic.pdf", item_id=None):
    form = {"item_id": str(item_id)} if item_id else {}
    return await user.client.post("/evidence", files={"file": (name, data)}, data=form)


async def test_rejects_wrong_file_type(make_user):
    user = await make_user()
    r = await upload(user, b"<html>not a pdf</html>", name="x.pdf")
    assert r.status_code == 415
    assert r.json()["error"]["code"] == "unsupported_file"


async def test_toeic_conflict_and_resolution(make_user, mock_llm, pg):
    mock_llm.on("process_evidence", toeic_extract())
    user = await make_user()
    item = (
        await user.client.post(
            "/items",
            json={
                "type": "language_test",
                "title": "TOEIC",
                "details": {"test": "TOEIC", "score": "850"},
            },
        )
    ).json()
    r = await upload(user, make_pdf(TOEIC_LINES))
    assert r.status_code == 202
    await drain_jobs()

    ev = (await user.client.get("/evidence")).json()["evidence"][0]
    assert ev["kind"] == "language_score" and ev["status"] == "processed"
    assert ev["expires_on"] == "2028-05-12" and ev["extracted"]["expires_on_estimated"] is True
    ocr = await pg.fetchval("select ocr_text from evidence where id = $1", uuid.UUID(ev["id"]))
    assert "123456789012" not in ocr and "[번호 삭제]" in ocr

    p = next(p for p in await pending(user) if p["kind"] == "attach_evidence")
    assert p["item_id"] == item["id"]
    assert p["payload"]["conflicts"] == [
        {"field": "score", "label": "점수", "item_value": "850", "evidence_value": "905"}
    ]
    assert {f["field"] for f in p["payload"]["fills"]} == {"test_date", "valid_until"}

    r = await user.client.post(
        f"/proposals/{p['id']}/accept",
        json={"edited_payload": {"resolutions": {"score": "evidence"}}},
    )
    assert r.status_code == 200, r.text
    detail = (await user.client.get(f"/items/{item['id']}")).json()
    assert detail["details"]["score"] == "905"
    assert detail["details"]["test_date"] == "2026-05-12"
    assert [e["id"] for e in detail["evidence"]] == [ev["id"]]
    assert any(s["evidence_id"] == ev["id"] for s in detail["sources"])


async def test_values_not_in_text_are_dropped(make_user, mock_llm):
    mock_llm.on("process_evidence", toeic_extract(score="990"))
    user = await make_user()
    await upload(user, make_pdf(TOEIC_LINES))
    await drain_jobs()
    ev = (await user.client.get("/evidence")).json()["evidence"][0]
    assert ev["extracted"]["score"] is None


async def test_unmatched_evidence_creates_item_proposal(make_user, mock_llm):
    mock_llm.on("process_evidence", toeic_extract())
    user = await make_user()
    await upload(user, make_pdf(TOEIC_LINES))
    await drain_jobs()
    proposals = await pending(user)
    assert sorted(p["kind"] for p in proposals) == ["attach_evidence", "create_item"]
    create = next(p for p in proposals if p["kind"] == "create_item")
    assert create["item"]["type"] == "language_test" and create["item"]["title"] == "TOEIC"
    r = await user.client.post("/proposals/bulk-accept", json={"ids": [p["id"] for p in proposals]})
    assert r.status_code == 200, r.text
    item = (await user.client.get("/items")).json()["items"][0]
    assert item["details"]["score"] == "905"


async def test_signed_url_and_public_visibility(make_user, mock_llm, anon):
    mock_llm.on("process_evidence", toeic_extract())
    alice, bob = await make_user(), await make_user()
    item = (
        await alice.client.post(
            "/items", json={"type": "language_test", "title": "TOEIC", "visibility": "public"}
        )
    ).json()
    ev = (await upload(alice, make_pdf(TOEIC_LINES), item_id=item["id"])).json()["evidence"]
    await drain_jobs()

    assert (await bob.client.get(f"/evidence/{ev['id']}/url")).status_code == 404
    url = (await alice.client.get(f"/evidence/{ev['id']}/url")).json()["url"]
    r = await anon.get(url.removeprefix("http://test/api/v1"))
    assert r.status_code == 200 and r.content.startswith(b"%PDF")

    handle = f"e{alice.id.hex[:10]}"
    await alice.client.patch("/me/profile", json={"handle": handle, "public_profile_enabled": True})
    attach = next(p for p in await pending(alice) if p["kind"] == "attach_evidence")
    await alice.client.post(f"/proposals/{attach['id']}/accept")
    body = (await anon.get(f"/public/{handle}")).json()
    assert body["items"][0]["evidence"] == []  # 비공개 증빙은 나오지 않는다
    assert (await anon.get(f"/public/{handle}/evidence/{ev['id']}")).status_code == 404

    await alice.client.patch(f"/evidence/{ev['id']}", json={"visibility": "public"})
    body = (await anon.get(f"/public/{handle}")).json()
    assert body["items"][0]["evidence"][0]["id"] == ev["id"]
    r = await anon.get(f"/public/{handle}/evidence/{ev['id']}", follow_redirects=False)
    assert r.status_code == 302

    r = await alice.client.delete(f"/evidence/{ev['id']}")
    assert r.status_code == 204
    assert (await anon.get(url.removeprefix("http://test/api/v1"))).status_code == 404


def test_demo_reader_and_validity_table():
    out = demo_evidence({"FILE_NAME": "toeic.pdf", "TEXT": "\n".join(TOEIC_LINES)})
    assert out["kind"] == "language_score" and out["title"] == "TOEIC"
    assert out["score"] == "905" and out["issued_on"] == "2026-05-12"
    assert demo_evidence({"FILE_NAME": "scan.png", "TEXT": ""})["kind"] == "other"
    from datetime import date

    assert estimate_expiry("토익 스피킹", date(2026, 2, 28)) == date(2028, 2, 28)
    assert estimate_expiry("JLPT N2", date(2026, 1, 1)) is None
