"""임베딩 어댑터(인계서 6장, 19장). 제공사는 OpenAI로 정했다(docs/decisions.md).

EMBEDDING_PROVIDER가 비어 있으면 None을 돌려주고, 호출하는 쪽은 임베딩 없이 동작한다.
입력 텍스트는 로그에 남기지 않는다.
"""

import httpx

from app.config import get_settings

OPENAI_URL = "https://api.openai.com/v1/embeddings"

# 테스트에서 가짜 응답을 끼우는 자리다.
_transport: httpx.AsyncBaseTransport | None = None


class EmbeddingError(Exception):
    pass


def set_transport(transport: httpx.AsyncBaseTransport | None) -> None:
    global _transport
    _transport = transport


async def embed(texts: list[str]) -> list[list[float]] | None:
    settings = get_settings()
    if not settings.embedding_provider:
        return None
    if settings.embedding_provider != "openai":
        raise EmbeddingError(f"지원하지 않는 EMBEDDING_PROVIDER: {settings.embedding_provider}")
    if not settings.openai_api_key:
        raise EmbeddingError("OPENAI_API_KEY가 설정되지 않았다.")
    body = {
        "model": settings.embedding_model,
        "input": texts,
        "dimensions": settings.embedding_dim,
    }
    async with httpx.AsyncClient(timeout=60.0, transport=_transport) as http:
        resp = await http.post(
            OPENAI_URL, json=body, headers={"Authorization": f"Bearer {settings.openai_api_key}"}
        )
    if resp.status_code >= 400:
        raise EmbeddingError(f"임베딩 API 오류: HTTP {resp.status_code}")
    data = sorted(resp.json()["data"], key=lambda d: d["index"])
    vectors = [d["embedding"] for d in data]
    if len(vectors) != len(texts) or any(len(v) != settings.embedding_dim for v in vectors):
        raise EmbeddingError("임베딩 개수나 차원이 설정(EMBEDDING_DIM)과 다르다.")
    return vectors
