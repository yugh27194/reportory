"""LLM·임베딩 키 점검: `uv run python -m app.check_llm`

키가 어디서 왔는지(.env 또는 시스템 환경 변수), 앞뒤 몇 글자, 실제로 API가 받아들이는지를 보여 준다.
키 전체는 출력하지 않는다.
"""

import asyncio
import os
from pathlib import Path

import httpx

from app.config import get_settings


def _mask(key: str) -> str:
    if not key:
        return "(비어 있음)"
    if len(key) < 30:
        return f"{key[:6]}… (길이 {len(key)}, 너무 짧다)"
    return f"{key[:10]}…{key[-4:]} (길이 {len(key)})"


def _source(name: str) -> str:
    in_file = False
    env_file = Path(".env")
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith(f"{name}=") and line.split("=", 1)[1].strip():
                in_file = True
    in_env = bool(os.environ.get(name))
    if in_file and in_env:
        return ".env 파일(시스템 환경 변수에도 같은 이름이 있지만 .env를 쓴다)"
    if in_file:
        return ".env 파일"
    if in_env:
        return "시스템 환경 변수(.env에는 값이 없다)"
    return "어디에도 없다"


async def check_anthropic() -> None:
    import anthropic

    s = get_settings()
    print(f"[Anthropic] LLM_PROVIDER = {s.llm_provider}")
    print(f"[Anthropic] 키 출처: {_source('ANTHROPIC_API_KEY')}")
    print(f"[Anthropic] 키: {_mask(s.anthropic_api_key)}")
    if not s.anthropic_api_key:
        print("  → api\\.env의 ANTHROPIC_API_KEY= 뒤에 키를 넣는다.")
        return
    key = s.anthropic_api_key
    if not key.startswith("sk-ant-"):
        print(
            "  ! Anthropic 키는 sk-ant- 로 시작한다(sk-ant-api03-, sk-ant-usr- 등). 다른 값이 들어갔는지 본다."
        )
    client = anthropic.AsyncAnthropic(api_key=s.anthropic_api_key, max_retries=0, timeout=30)
    for model in (s.llm_model_extract, s.llm_model_light):
        try:
            await client.models.retrieve(model)
            print(f"  ✓ {model}: 키와 모델 모두 정상이다.")
        except anthropic.AuthenticationError:
            print(
                f"  ✗ {model}: 키가 거절됐다(401). 콘솔에서 키가 삭제·비활성화되지 않았는지 보고, 새 키를 만들어 넣는다."
            )
            return
        except anthropic.NotFoundError:
            print(f"  ✗ {model}: 이 모델 이름을 찾을 수 없다(404). LLM_MODEL_* 값을 확인한다.")
        except anthropic.APIStatusError as exc:
            print(f"  ? {model}: 확인 실패(HTTP {exc.status_code}): {_api_message(exc)}")
            return
        except anthropic.APIError as exc:
            print(f"  ? {model}: 확인 실패({type(exc).__name__}).")
            return
    # 실제로 아주 짧은 요청을 한 번 보낸다(크레딧·결제 문제는 여기서 드러난다).
    try:
        await client.messages.create(
            model=s.llm_model_light,
            max_tokens=8,
            messages=[{"role": "user", "content": "ping"}],
        )
        print("  ✓ 실제 요청도 성공했다. 분석이 동작한다.")
    except anthropic.APIStatusError as exc:
        print(f"  ✗ 실제 요청 실패(HTTP {exc.status_code}): {_api_message(exc)}")


def _api_message(exc) -> str:
    """API가 돌려준 오류 설명만 꺼낸다(키는 들어 있지 않다)."""
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        err = body.get("error") or {}
        if isinstance(err, dict) and err.get("message"):
            return str(err["message"])[:300]
    return str(getattr(exc, "message", exc))[:300]


async def check_openai() -> None:
    s = get_settings()
    print(f"[OpenAI] EMBEDDING_PROVIDER = {s.embedding_provider or '(꺼짐)'}")
    if not s.embedding_provider:
        return
    print(f"[OpenAI] 키 출처: {_source('OPENAI_API_KEY')}")
    print(f"[OpenAI] 키: {_mask(s.openai_api_key)}")
    if not s.openai_api_key:
        return
    if "..." in s.openai_api_key or len(s.openai_api_key) < 40:
        print(
            "  ! 이 값은 키 목록 화면에 보이는 가린 표시(sk-...abcd)다. 진짜 키가 아니다.\n"
            "    platform.openai.com → API keys → Create new secret key를 누르고,\n"
            "    만든 직후 한 번만 보이는 긴 키(sk-proj-로 시작) 전체를 복사해 넣는다."
        )
        return
    try:
        async with httpx.AsyncClient(timeout=30) as http:
            r = await http.get(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {s.openai_api_key}"},
            )
    except httpx.HTTPError as exc:
        print(f"  ? OpenAI에 연결하지 못했다({type(exc).__name__}). 인터넷·방화벽을 확인한다.")
        return
    print("  ✓ 키가 정상이다." if r.status_code == 200 else f"  ✗ 거절됐다(HTTP {r.status_code}).")


async def main() -> None:
    await check_anthropic()
    print()
    await check_openai()


if __name__ == "__main__":
    asyncio.run(main())
