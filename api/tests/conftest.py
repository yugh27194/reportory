"""테스트 공통 준비.

TEST_DATABASE_URL(기본: 로컬 Postgres 54322 포트)에 테스트 DB를 새로 만들고,
Supabase 대역(supabase/local/supabase_shim.sql)과 마이그레이션을 적용한다. LLM은 mock이다.
"""

import os
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import asyncpg
import jwt
import pytest

ROOT = Path(__file__).resolve().parents[2]
ADMIN_URL = os.environ.get(
    "TEST_DATABASE_ADMIN_URL", "postgresql://postgres@localhost:54322/postgres"
)
TEST_DB = os.environ.get("TEST_DATABASE_NAME", "reportory_test")
JWT_SECRET = "test-jwt-secret-at-least-32-bytes-long"
CRON_SECRET = "test-cron-secret"

_base = ADMIN_URL.rsplit("/", 1)[0]
os.environ["DATABASE_URL"] = f"{_base.replace('postgresql://', 'postgresql+asyncpg://')}/{TEST_DB}"
os.environ["SUPABASE_JWT_SECRET"] = JWT_SECRET
os.environ["SUPABASE_JWKS_URL"] = ""
os.environ["LLM_PROVIDER"] = "mock"
os.environ["CRON_SECRET"] = CRON_SECRET
os.environ["EMBEDDING_PROVIDER"] = ""

from httpx import ASGITransport, AsyncClient  # noqa: E402

from app.db import dispose_engine  # noqa: E402
from app.llm.client import LLMClient, MockProvider, set_llm  # noqa: E402
from app.main import create_app  # noqa: E402
from app.worker import run_once  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
async def database():
    admin = await asyncpg.connect(ADMIN_URL)
    await admin.execute(f'drop database if exists "{TEST_DB}" with (force)')
    await admin.execute(f'create database "{TEST_DB}"')
    await admin.close()
    conn = await asyncpg.connect(f"{_base}/{TEST_DB}")
    await conn.execute((ROOT / "supabase/local/supabase_shim.sql").read_text())
    for path in sorted((ROOT / "supabase/migrations").glob("*.sql")):
        await conn.execute(path.read_text())
    await conn.close()
    yield
    await dispose_engine()


@pytest.fixture
async def pg():
    conn = await asyncpg.connect(f"{_base}/{TEST_DB}")
    yield conn
    await conn.close()


@pytest.fixture(autouse=True)
async def clean_jobs(pg):
    await pg.execute("delete from jobs")


@pytest.fixture
def mock_llm():
    provider = MockProvider()
    set_llm(LLMClient(provider, {"extract": "mock-extract", "light": "mock-light"}))
    yield provider
    set_llm(None)


def make_token(user_id: uuid.UUID, *, expires_in: int = 3600, secret: str = JWT_SECRET) -> str:
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "sub": str(user_id),
            "aud": "authenticated",
            "role": "authenticated",
            "iat": now,
            "exp": now + timedelta(seconds=expires_in),
        },
        secret,
        algorithm="HS256",
    )


class User:
    def __init__(self, user_id: uuid.UUID, client: AsyncClient):
        self.id = user_id
        self.client = client


@pytest.fixture
async def app_transport():
    return ASGITransport(app=create_app())


@pytest.fixture
async def make_user(pg, app_transport):
    clients: list[AsyncClient] = []

    async def _make(*, consent: bool = True) -> User:
        user_id = uuid.uuid4()
        await pg.execute(
            "insert into auth.users (id, email) values ($1, $2)",
            user_id,
            f"{user_id.hex[:8]}@example.com",
        )
        client = AsyncClient(
            transport=app_transport,
            base_url="http://test/api/v1",
            headers={"Authorization": f"Bearer {make_token(user_id)}"},
        )
        clients.append(client)
        if consent:
            assert (await client.post("/me/consent")).status_code == 200
        return User(user_id, client)

    yield _make
    for c in clients:
        await c.aclose()


@pytest.fixture
async def anon(app_transport):
    async with AsyncClient(transport=app_transport, base_url="http://test/api/v1") as c:
        yield c


async def drain_jobs(limit: int = 50) -> int:
    n = 0
    while n < limit and await run_once():
        n += 1
    return n
