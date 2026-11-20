"""DB 접속과 user_id 필터 강제(인계서 8.4절 추가 규칙, 14장).

API 서버는 service role 권한으로 접속하므로 RLS를 우회한다. 그래서 사용자 데이터에 닿는
쿼리는 모두 `UserDB`를 거치고, `UserDB`는 SQL에 `:user_id` 조건이 없으면 실행을 거부한다.
`SystemDB`는 작업 큐, 전역 테이블처럼 사용자 범위 밖의 쿼리에만 쓴다.
"""

import json
from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine

from app.auth import current_user_id
from app.config import get_settings

_engine: AsyncEngine | None = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = create_async_engine(get_settings().database_url, pool_pre_ping=True)
    return _engine


async def dispose_engine() -> None:
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None


def as_json(value: Any) -> str:
    """jsonb 파라미터는 문자열로 넘기고 SQL에서 cast(:x as jsonb)로 받는다."""
    return json.dumps(value, ensure_ascii=False, default=str)


class _Base:
    def __init__(self, conn: AsyncConnection):
        self.conn = conn

    async def _run(self, sql: str, params: dict[str, Any]):
        return await self.conn.execute(text(sql), params)

    async def all(self, sql: str, **params: Any) -> list[dict]:
        return [
            dict(r) for r in (await self._run(self._check(sql), self._params(params))).mappings()
        ]

    async def one(self, sql: str, **params: Any) -> dict | None:
        row = (await self._run(self._check(sql), self._params(params))).mappings().first()
        return dict(row) if row else None

    async def scalar(self, sql: str, **params: Any) -> Any:
        return (await self._run(self._check(sql), self._params(params))).scalar()

    async def execute(self, sql: str, **params: Any) -> int:
        return (await self._run(self._check(sql), self._params(params))).rowcount

    def _check(self, sql: str) -> str:
        return sql

    def _params(self, params: dict[str, Any]) -> dict[str, Any]:
        return params


class SystemDB(_Base):
    """사용자 범위 밖의 쿼리(작업 큐, 전역 테이블, 공개 프로필 조회)."""


class UserDB(_Base):
    """모든 쿼리에 `:user_id`를 강제한다."""

    def __init__(self, conn: AsyncConnection, user_id: UUID):
        super().__init__(conn)
        self.user_id = user_id

    def _check(self, sql: str) -> str:
        if ":user_id" not in sql:
            raise RuntimeError("UserDB 쿼리에는 :user_id 조건이 있어야 한다.")
        return sql

    def _params(self, params: dict[str, Any]) -> dict[str, Any]:
        if "user_id" in params and params["user_id"] != self.user_id:
            raise RuntimeError("UserDB에 다른 user_id를 넘길 수 없다.")
        return {**params, "user_id": self.user_id}

    @property
    def system(self) -> SystemDB:
        return SystemDB(self.conn)


async def get_conn() -> AsyncIterator[AsyncConnection]:
    async with get_engine().begin() as conn:
        yield conn


async def get_user_db(
    user_id: UUID = Depends(current_user_id),
    conn: AsyncConnection = Depends(get_conn),
) -> UserDB:
    return UserDB(conn, user_id)


async def get_system_db(conn: AsyncConnection = Depends(get_conn)) -> SystemDB:
    return SystemDB(conn)
