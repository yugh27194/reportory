"""임베딩 어댑터. 제공사·차원은 19장에서 확정한다.

EMBEDDING_PROVIDER가 비어 있으면 None을 돌려주고, 호출하는 쪽은 임베딩 없이 동작한다.
"""

from app.config import get_settings


class EmbeddingNotConfigured(Exception):
    pass


async def embed(texts: list[str]) -> list[list[float]] | None:
    settings = get_settings()
    if not settings.embedding_provider:
        return None
    raise EmbeddingNotConfigured(
        f"임베딩 제공사 '{settings.embedding_provider}' 어댑터가 아직 없다(19장 확정 후 추가한다)."
    )
