"""임베딩 기반 중복 의심과 KNOWN_ITEMS 선택(인계서 10.2절)."""

import json

import httpx
import pytest

from app import embeddings
from app.config import get_settings
from app.db import UserDB, get_engine
from app.jobs.extract_entry import known_items
from app.services.similarity import cosine
from tests.conftest import drain_jobs
from tests.test_flow import hackathon_extraction, pending, write_and_extract

DIM = 1536


def topic_vector(text: str) -> list[float]:
    """주제 단어로 방향을 정하는 가짜 임베딩. 같은 주제면 코사인 1, 다르면 0이다."""
    v = [0.0] * DIM
    for i, word in enumerate(["해커톤", "멘토링", "딥러닝"]):
        if word in text:
            v[i] = 1.0
    if not any(v):
        v[DIM - 1] = 1.0
    return v


@pytest.fixture
def fake_embeddings(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "embedding_provider", "openai")
    monkeypatch.setattr(settings, "openai_api_key", "test-key")

    def handler(request: httpx.Request) -> httpx.Response:
        texts = json.loads(request.content)["input"]
        data = [{"index": i, "embedding": topic_vector(t)} for i, t in enumerate(texts)]
        return httpx.Response(200, json={"data": data})

    embeddings.set_transport(httpx.MockTransport(handler))
    yield
    embeddings.set_transport(None)


def test_cosine():
    assert cosine([1, 0], [1, 0]) == 1.0
    assert cosine([1, 0], [0, 1]) == 0.0
    assert cosine([0, 0], [1, 0]) == 0.0


async def test_similar_title_is_flagged_as_duplicate(make_user, mock_llm, fake_embeddings):
    user = await make_user()
    existing = (
        await user.client.post("/items", json={"type": "project", "title": "해커톤 백엔드 개발"})
    ).json()
    await drain_jobs()
    mock_llm.on("extract_entry", hackathon_extraction)  # 후보 제목: "OO 해커톤 프로젝트"
    await write_and_extract(user)
    project = next(p for p in await pending(user) if p["item"]["type"] == "project")
    award = next(p for p in await pending(user) if p["item"]["type"] == "award")
    assert project["possible_duplicate_of"] == existing["id"]
    assert award["possible_duplicate_of"] is None  # 유형이 다르면 비교하지 않는다


async def test_embedding_failure_falls_back_to_exact_title(make_user, mock_llm, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "embedding_provider", "openai")
    monkeypatch.setattr(settings, "openai_api_key", "test-key")
    embeddings.set_transport(httpx.MockTransport(lambda r: httpx.Response(500)))
    try:
        user = await make_user()
        await user.client.post("/items", json={"type": "project", "title": "OO 해커톤 프로젝트"})
        mock_llm.on("extract_entry", hackathon_extraction)
        data = await write_and_extract(user)
        job = (await user.client.get(f"/jobs/{data['job_id']}")).json()
        assert job["status"] == "succeeded"
        project = next(p for p in await pending(user) if p["item"]["type"] == "project")
        assert project["possible_duplicate_of"] is not None
    finally:
        embeddings.set_transport(None)


async def test_known_items_over_limit_include_similar_and_ongoing(make_user, fake_embeddings):
    user = await make_user()
    deep = (
        await user.client.post("/items", json={"type": "project", "title": "딥러닝 분류 모델"})
    ).json()
    ongoing = (
        await user.client.post(
            "/items", json={"type": "activity", "title": "학회 운영진", "is_ongoing": True}
        )
    ).json()
    for i in range(45):
        await user.client.post("/items", json={"type": "activity", "title": f"봉사 {i}"})
    await drain_jobs()

    async with get_engine().begin() as conn:
        ctx = await known_items(UserDB(conn, user.id), "딥러닝 모델 정확도가 올랐다")
    ids = {c["id"] for c in ctx}
    assert deep["id"] in ids  # 오래됐지만 일기와 유사하다
    assert ongoing["id"] in ids  # 진행 중이다
    assert len(ctx) <= 20 + 20 + 1
