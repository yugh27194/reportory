"""요약·알림·내보내기·계정 삭제(인계서 10.5절, 11.8절, 11.10절)."""

import io
import json
import uuid
import zipfile
from datetime import date

import httpx

from app.jobs import account
from app.routers.internal import previous_month, week_range
from app.storage import get_storage
from tests.conftest import CRON_SECRET, drain_jobs
from tests.pdfgen import make_pdf
from tests.test_evidence import TOEIC_LINES, toeic_extract, upload
from tests.test_flow import hackathon_extraction, pending, write_and_extract

CRON = {"X-Cron-Secret": CRON_SECRET}


def test_period_ranges():
    assert week_range(date(2026, 11, 29)) == (date(2026, 11, 23), date(2026, 11, 29))
    assert previous_month(date(2026, 12, 1)) == (date(2026, 11, 1), date(2026, 11, 30))
    assert previous_month(date(2026, 1, 1)) == (date(2025, 12, 1), date(2025, 12, 31))


async def test_weekly_summary_and_notifications(make_user, mock_llm, anon, pg):
    mock_llm.on("extract_entry", hackathon_extraction)
    user = await make_user()
    start, end = week_range(date.today())
    await write_and_extract(user, entry_date=start.isoformat())
    for p in await pending(user):
        await user.client.post(f"/proposals/{p['id']}/accept")
    item_ids = {i["id"] for i in (await user.client.get("/items")).json()["items"]}

    def summary(v):
        changes = v["CHANGES"]
        return {
            "summary_md": "해커톤에서 백엔드를 맡았다. 상금 500만 원을 받았다.",
            "highlights": [
                {"item_id": changes[0]["id"], "text": "해커톤 프로젝트"},
                {"item_id": str(uuid.uuid4()), "text": "지어낸 항목"},
            ],
        }

    mock_llm.on("period_summary", summary)
    r = await anon.post("/internal/cron/weekly_summary", headers=CRON)
    assert r.status_code == 200 and r.json()["users"] >= 1
    await drain_jobs()
    rows = (await user.client.get("/summaries", params={"period": "week"})).json()["summaries"]
    assert len(rows) == 1
    s = rows[0]
    assert s["summary_md"] == "해커톤에서 백엔드를 맡았다."  # 근거에 없는 숫자 문장은 지운다
    assert len(s["highlights"]) == 1 and s["highlights"][0]["item_id"] in item_ids

    notes = (await user.client.get("/notifications")).json()
    assert notes["unread"] >= 2
    assert {"proposals_ready", "summary_ready"} <= {n["type"] for n in notes["notifications"]}
    await user.client.post("/notifications/read", json={})
    assert (await user.client.get("/notifications")).json()["unread"] == 0

    # 같은 주를 다시 돌려도 요약은 하나이고 알림도 다시 보내지 않는다.
    await anon.post("/internal/cron/weekly_summary", headers=CRON)
    await drain_jobs()
    assert len((await user.client.get("/summaries")).json()["summaries"]) == 1
    assert (await user.client.get("/notifications")).json()["unread"] == 0


async def test_evidence_expiry_notification(make_user, mock_llm, anon, pg):
    mock_llm.on("process_evidence", toeic_extract())
    user = await make_user()
    ev = (await upload(user, make_pdf(TOEIC_LINES))).json()["evidence"]
    await drain_jobs()
    await pg.execute(
        "update evidence set expires_on = current_date + 10 where id = $1", uuid.UUID(ev["id"])
    )
    await anon.post("/internal/cron/evidence_expiry", headers=CRON)
    await anon.post("/internal/cron/evidence_expiry", headers=CRON)
    notes = (await user.client.get("/notifications")).json()["notifications"]
    assert [n["type"] for n in notes].count("evidence_expiry") == 1


async def test_export_zip(make_user, mock_llm, anon):
    mock_llm.on("extract_entry", hackathon_extraction)
    mock_llm.on("process_evidence", toeic_extract())
    user = await make_user()
    await write_and_extract(user)
    for p in await pending(user):
        await user.client.post(f"/proposals/{p['id']}/accept")
    await upload(user, make_pdf(TOEIC_LINES))
    await drain_jobs()
    job_id = (await user.client.post("/export")).json()["job_id"]
    await drain_jobs()
    url = (await user.client.get(f"/export/{job_id}/url")).json()["url"]
    data = (await anon.get(url.removeprefix("http://test/api/v1"))).content
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        names = set(z.namelist())
        assert {"resume.json", "items.json", "entries.json", "applications.json"} <= names
        assert any(n.startswith("evidence/") and n.endswith(".pdf") for n in names)
        resume = json.loads(z.read("resume.json"))
        assert resume["projects"] and resume["awards"]
        assert resume["meta"]["canonical"].startswith("https://jsonresume.org")


async def test_delete_account_removes_files_and_rows(make_user, mock_llm, pg):
    mock_llm.on("process_evidence", toeic_extract())
    user = await make_user()
    await upload(user, make_pdf(TOEIC_LINES))
    await drain_jobs()
    r = await user.client.request("DELETE", "/account", json={"confirm": "삭제"})
    assert r.status_code == 422
    r = await user.client.request("DELETE", "/account", json={"confirm": "계정 삭제"})
    assert r.status_code == 202
    await drain_jobs()
    assert await pg.fetchval("select count(*) from auth.users where id = $1", user.id) == 0
    assert await pg.fetchval("select count(*) from evidence where user_id = $1", user.id) == 0
    assert await get_storage().delete_prefix("evidence", f"{user.id}/") == 0


async def test_delete_account_uses_admin_api_when_configured(make_user, monkeypatch):
    from app.config import get_settings

    s = get_settings()
    monkeypatch.setattr(s, "supabase_url", "https://x.supabase.co")
    monkeypatch.setattr(s, "supabase_service_role_key", "service-key")
    calls = []
    account.set_transport(
        httpx.MockTransport(
            lambda req: calls.append((req.method, req.url.path)) or httpx.Response(200, json={})
        )
    )
    try:
        user = await make_user()
        await user.client.request("DELETE", "/account", json={"confirm": "계정 삭제"})
        await drain_jobs()
        assert calls == [("DELETE", f"/auth/v1/admin/users/{user.id}")]
    finally:
        account.set_transport(None)


async def test_demo_period_summary_keeps_lines(make_user, monkeypatch, anon):
    from app.config import get_settings
    from app.llm import client as llm_client

    monkeypatch.setattr(get_settings(), "llm_provider", "demo")
    llm_client.set_llm(None)
    try:
        user = await make_user()
        start, _ = week_range(date.today())
        await user.client.post(
            "/entries",
            json={
                "entry_date": start.isoformat(),
                "body": "오늘 OO 해커톤에서 팀원 3명과 FastAPI로 백엔드를 맡았다.",
            },
        )
        await drain_jobs()
        for p in await pending(user):
            await user.client.post(f"/proposals/{p['id']}/accept")
        await anon.post("/internal/cron/weekly_summary", headers=CRON)
        await drain_jobs()
        s = (await user.client.get("/summaries")).json()["summaries"][0]
        assert s["summary_md"].startswith("- ")
        assert "항목 1개를 승인했다" in s["summary_md"]
    finally:
        llm_client.set_llm(None)
