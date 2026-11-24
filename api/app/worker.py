"""DB 기반 작업 큐 워커(인계서 13.1절). 실행: `python -m app.worker`."""

import asyncio
import logging
import signal
from uuid import UUID

from app.config import get_settings
from app.db import SystemDB, UserDB, as_json, get_engine
from app.jobs.registry import HANDLERS

log = logging.getLogger("reportory.worker")


async def requeue_stuck_jobs(minutes: int | None = None) -> int:
    minutes = minutes or get_settings().stuck_job_minutes
    async with get_engine().begin() as conn:
        return await SystemDB(conn).execute(
            """update jobs set status = 'queued', locked_at = null
               where status = 'running' and locked_at < now() - make_interval(mins => :m)""",
            m=minutes,
        )


async def _claim() -> dict | None:
    async with get_engine().begin() as conn:
        return await SystemDB(conn).one(
            """update jobs set status = 'running', locked_at = now()
               where id = (
                 select id from jobs where status = 'queued' and run_after <= now()
                 order by created_at for update skip locked limit 1)
               returning id, user_id, type, payload, attempts, max_attempts"""
        )


def _error_text(exc: BaseException) -> str:
    # 사용자 데이터가 섞이지 않도록 예외 종류와 짧은 메시지만 남긴다.
    return f"{type(exc).__name__}: {str(exc)[:300]}"


async def run_once() -> bool:
    """대기 작업 하나를 처리한다. 처리한 작업이 없으면 False."""
    job = await _claim()
    if job is None:
        return False
    spec = HANDLERS.get(job["type"])
    job_id: UUID = job["id"]
    try:
        if spec is None:
            raise LookupError(f"알 수 없는 작업 유형: {job['type']}")
        if job["user_id"] is None:
            raise LookupError("사용자 작업에 user_id가 없다.")
        async with get_engine().begin() as conn:
            result = await spec.run(UserDB(conn, job["user_id"]), job["payload"])
            await SystemDB(conn).execute(
                """update jobs set status = 'succeeded', result = cast(:r as jsonb),
                     locked_at = null, last_error = null where id = :id""",
                id=job_id,
                r=as_json(result),
            )
        log.info("job succeeded id=%s type=%s", job_id, job["type"])
    except Exception as exc:  # noqa: BLE001 - 어떤 실패든 재시도 규칙으로 처리한다
        await _fail(job, spec, exc)
    return True


async def _fail(job: dict, spec, exc: BaseException) -> None:
    attempts = job["attempts"] + 1
    final = attempts >= job["max_attempts"] or spec is None
    log.warning(
        "job failed id=%s type=%s attempt=%s final=%s error=%s",
        job["id"],
        job["type"],
        attempts,
        final,
        type(exc).__name__,
    )
    async with get_engine().begin() as conn:
        await SystemDB(conn).execute(
            """update jobs set attempts = :a, last_error = :err, locked_at = null,
                 status = cast(:status as job_status),
                 run_after = case when :final then run_after
                                  else now() + make_interval(mins => :delay) end
               where id = :id""",
            id=job["id"],
            a=attempts,
            err=_error_text(exc),
            delay=2**attempts,
            final=final,
            status="failed" if final else "queued",
        )
        if final and spec is not None and spec.on_final_failure and job["user_id"]:
            await spec.on_final_failure(UserDB(conn, job["user_id"]), job["payload"])


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    settings = get_settings()
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:
            # Windows 이벤트 루프는 신호 처리기를 지원하지 않는다. Ctrl+C는 KeyboardInterrupt로 끝난다.
            pass
    log.info("worker started")
    await requeue_stuck_jobs()
    while not stop.is_set():
        processed = await run_once()
        if not processed:
            try:
                await asyncio.wait_for(stop.wait(), timeout=settings.worker_poll_seconds)
            except TimeoutError:
                pass
    log.info("worker stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
