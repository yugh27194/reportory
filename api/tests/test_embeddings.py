"""OpenAI 임베딩 어댑터와 embed_item 작업(인계서 13.1절)."""

import json

import httpx
import pytest

from app import embeddings
from app.config import get_settings
from tests.conftest import drain_jobs


@pytest.fixture
def openai_embeddings(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "embedding_provider", "openai")
    monkeypatch.setattr(settings, "openai_api_key", "test-key")
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        requests.append((request, body))
        data = [
            {"index": i, "embedding": [0.001 * (i + 1)] * body["dimensions"]}
            for i in range(len(body["input"]))
        ]
        return httpx.Response(200, json={"data": list(reversed(data))})

    embeddings.set_transport(httpx.MockTransport(handler))
    yield requests
    embeddings.set_transport(None)


async def test_embed_calls_openai_and_orders_by_index(openai_embeddings):
    vectors = await embeddings.embed(["a", "b"])
    request, body = openai_embeddings[0]
    assert request.headers["Authorization"] == "Bearer test-key"
    assert body == {"model": "text-embedding-3-small", "input": ["a", "b"], "dimensions": 1536}
    assert [v[0] for v in vectors] == [0.001, 0.002]


async def test_embed_without_provider_returns_none():
    assert await embeddings.embed(["a"]) is None


async def test_approved_item_gets_embedding(make_user, pg, openai_embeddings):
    user = await make_user()
    item = (
        await user.client.post("/items", json={"type": "project", "title": "임베딩 시험"})
    ).json()
    await drain_jobs()
    has = await pg.fetchval(
        "select embedding is not null from items where id = $1",
        __import__("uuid").UUID(item["id"]),
    )
    assert has
    assert "임베딩 시험" in openai_embeddings[0][1]["input"][0]


async def test_openai_without_key_skips_embeddings(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "embedding_provider", "openai")
    monkeypatch.setattr(settings, "openai_api_key", "")
    assert await embeddings.embed(["a"]) is None
