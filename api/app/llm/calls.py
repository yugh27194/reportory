"""llm_calls 기록(인계서 10.1절). 입력·출력 본문은 남기지 않는다.

작업이 실패해 핸들러 트랜잭션이 롤백돼도 비용 기록은 남아야 하므로 별도 트랜잭션으로 쓴다.
"""

from app.db import SystemDB, UserDB, get_engine
from app.llm.client import CallLogger


def call_logger(db: UserDB) -> CallLogger:
    async def log_call(row: dict) -> None:
        async with get_engine().begin() as conn:
            await SystemDB(conn).execute(
                """insert into llm_calls (user_id, purpose, provider, model, prompt_version,
                     input_tokens, output_tokens, latency_ms, success, error)
                   values (:user_id, :purpose, :provider, :model, :prompt_version, :input_tokens,
                     :output_tokens, :latency_ms, :success, :error)""",
                **{**row, "user_id": db.user_id},
            )

    return log_call


def system_call_logger() -> CallLogger:
    """사용자 없이 도는 정기 작업(공고 수집)용."""

    async def log_call(row: dict) -> None:
        async with get_engine().begin() as conn:
            await SystemDB(conn).execute(
                """insert into llm_calls (user_id, purpose, provider, model, prompt_version,
                     input_tokens, output_tokens, latency_ms, success, error)
                   values (null, :purpose, :provider, :model, :prompt_version, :input_tokens,
                     :output_tokens, :latency_ms, :success, :error)""",
                **{k: v for k, v in row.items() if k != "user_id"},
            )

    return log_call
