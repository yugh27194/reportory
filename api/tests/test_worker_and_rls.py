"""워커 재시도와 RLS(인계서 13.1절, Phase 0 완료 기준)."""

import json
import uuid

from tests.conftest import CRON_SECRET, drain_jobs, make_token


async def _job(pg, user_id, payload, max_attempts=3):
    return await pg.fetchval(
        """insert into jobs (user_id, type, payload, max_attempts)
           values ($1, 'noop', $2::jsonb, $3) returning id""",
        user_id,
        json.dumps(payload),
        max_attempts,
    )


async def test_dummy_job_succeeds(make_user, pg):
    user = await make_user()
    job_id = await _job(pg, user.id, {})
    await drain_jobs()
    r = await user.client.get(f"/jobs/{job_id}")
    assert r.json()["status"] == "succeeded"
    assert r.json()["result"] == {"ok": True}


async def test_failed_job_retries_with_backoff_then_fails(make_user, pg):
    user = await make_user()
    job_id = await _job(pg, user.id, {"fail": True}, max_attempts=2)
    await drain_jobs()
    row = await pg.fetchrow(
        "select status, attempts, run_after > now() + interval '1 minute' as later, last_error "
        "from jobs where id = $1",
        job_id,
    )
    assert (row["status"], row["attempts"], row["later"]) == ("queued", 1, True)
    assert row["last_error"].startswith("RuntimeError")

    await pg.execute("update jobs set run_after = now() where id = $1", job_id)
    await drain_jobs()
    row = await pg.fetchrow("select status, attempts from jobs where id = $1", job_id)
    assert (row["status"], row["attempts"]) == ("failed", 2)


async def test_extraction_failure_marks_entry_failed(make_user, mock_llm, pg):
    mock_llm.on("extract_entry", lambda v: {"is_relevant": "not-a-bool-or-list", "items": 3})
    user = await make_user()
    r = await user.client.post("/entries", json={"entry_date": "2026-11-18", "body": "일기"})
    job_id = uuid.UUID(r.json()["job_id"])
    await pg.execute("update jobs set max_attempts = 1 where id = $1", job_id)
    await drain_jobs()
    assert mock_llm.calls == ["extract_entry", "extract_entry"]  # 검증 실패 후 한 번 더 부른다
    entry = (await user.client.get(f"/entries/{r.json()['entry']['id']}")).json()
    assert entry["extraction_status"] == "failed"
    calls = await pg.fetch("select success from llm_calls where user_id = $1", user.id)
    assert [c["success"] for c in calls] == [False, False]


async def test_stuck_jobs_are_requeued(make_user, pg, anon):
    user = await make_user()
    job_id = await _job(pg, user.id, {})
    await pg.execute(
        "update jobs set status = 'running', locked_at = now() - interval '20 minutes' "
        "where id = $1",
        job_id,
    )
    r = await anon.post("/internal/cron/requeue_stuck_jobs")
    assert r.status_code == 403
    r = await anon.post("/internal/cron/requeue_stuck_jobs", headers={"X-Cron-Secret": CRON_SECRET})
    assert r.json()["requeued"] == 1
    assert await pg.fetchval("select status from jobs where id = $1", job_id) == "queued"


async def test_expired_or_forged_token_is_rejected(anon):
    uid = uuid.uuid4()
    for token in (make_token(uid, expires_in=-10), make_token(uid, secret="x" * 40)):
        r = await anon.get("/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 401


async def test_rls_isolates_users(make_user, pg):
    alice, bob = await make_user(), await make_user()
    await alice.client.post("/entries", json={"entry_date": "2026-11-18", "body": "앨리스 일기"})
    await bob.client.post("/entries", json={"entry_date": "2026-11-18", "body": "밥 일기"})
    await alice.client.post("/items", json={"type": "award", "title": "앨리스 상"})

    async def as_user(user_id, sql):
        async with pg.transaction():
            await pg.execute("set local role authenticated")
            await pg.execute(
                "select set_config('request.jwt.claims', $1, true)",
                json.dumps({"sub": str(user_id), "role": "authenticated"}),
            )
            return await pg.fetch(sql)

    rows = await as_user(alice.id, "select body from entries")
    assert [r["body"] for r in rows] == ["앨리스 일기"]
    rows = await as_user(bob.id, "select title from items")
    assert rows == []
    rows = await as_user(bob.id, "select id from profiles")
    assert [r["id"] for r in rows] == [bob.id]
    # 다른 사용자 id로 쓰기를 시도하면 RLS가 막는다.
    try:
        await as_user(
            bob.id,
            f"insert into entries (user_id, entry_date, body) "
            f"values ('{alice.id}', '2026-11-18', 'x')",
        )
        raise AssertionError("RLS가 다른 사용자 행 쓰기를 막지 못했다")
    except Exception as exc:  # noqa: BLE001
        assert "row-level security" in str(exc)
    # 작업 큐는 자기 작업만 조회된다.
    rows = await as_user(alice.id, "select user_id from jobs")
    assert rows and {r["user_id"] for r in rows} == {alice.id}
