"""Anthropic 어댑터: 구조화 출력 요청 모양, 오류 분류, 워커의 즉시 실패(실제 API 대신 가짜 응답)."""

import json

import httpx2
import pytest
from anthropic import AsyncAnthropic, DefaultAsyncHttpxClient

from app.llm.client import AnthropicProvider, LLMClient, LLMError, set_llm
from app.llm.schemas import ExtractionResult
from tests.conftest import drain_jobs
from tests.test_flow import HACKATHON


def fake_client(handler) -> AsyncAnthropic:
    return AsyncAnthropic(
        api_key="test-key",
        max_retries=0,
        http_client=DefaultAsyncHttpxClient(transport=httpx2.MockTransport(handler)),
    )


def message(text: str, stop_reason: str = "end_turn") -> dict:
    return {
        "id": "msg_1",
        "type": "message",
        "role": "assistant",
        "model": "claude-sonnet-5-5",
        "content": [
            {"type": "thinking", "thinking": "", "signature": "s"},
            {"type": "text", "text": text},
        ],
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {"input_tokens": 100, "output_tokens": 50},
    }


EXTRACTION = {
    "is_relevant": True,
    "entry_summary": "해커톤에서 백엔드를 맡았다.",
    "items": [
        {
            "action": "create",
            "target_item_id": None,
            "type": "project",
            "title": "OO 해커톤 백엔드",
            "organization": None,
            "role": "백엔드",
            "start_date": None,
            "end_date": None,
            "is_ongoing": None,
            "summary_append": "팀원 3명과 FastAPI로 백엔드를 맡았다.",
            "skills": ["FastAPI"],
            "metrics": [],
            "details": {"team_size": 3, "rank": None, "repo_url": None},
            "quote": "팀원 3명과 FastAPI로 백엔드를 맡았다",
            "confidence": 0.9,
        }
    ],
    "application_updates": [],
    "followups": [],
}


async def test_request_uses_structured_output_not_forced_tool():
    seen = {}

    def handler(req: httpx2.Request) -> httpx2.Response:
        seen["body"] = json.loads(req.content)
        seen["beta"] = req.headers.get("anthropic-beta", "")
        return httpx2.Response(200, json=message(json.dumps(EXTRACTION, ensure_ascii=False)))

    client = LLMClient(
        AnthropicProvider("", client=fake_client(handler)),
        {"extract": "claude-sonnet-5-5", "light": "claude-haiku-5-5"},
        {"extract": "medium", "light": "low"},
    )
    out = await client.complete_json(
        "extract_entry",
        "extract_entry",
        {
            "ENTRY_DATE": "2026-11-25",
            "ENTRY": HACKATHON,
            "KNOWN_ITEMS": [],
            "OPEN_APPLICATIONS": [],
        },
        ExtractionResult,
        "extract",
    )
    body = seen["body"]
    assert "tool_choice" not in body and "tools" not in body
    fmt = body["output_config"]["format"]
    assert fmt["type"] == "json_schema" and fmt["schema"]["additionalProperties"] is False
    assert body["output_config"]["effort"] == "medium"
    assert body["fallbacks"] == "default" and "server-side-fallback-2026-07-01" in seen["beta"]
    # 구조화 출력이 채운 null details 키는 지운다.
    assert out.items[0].details == {"team_size": 3}


async def test_haiku_has_no_fallback():
    seen = {}

    def handler(req):
        seen["body"] = json.loads(req.content)
        return httpx2.Response(200, json=message('{"summary_md": "요약", "highlights": []}'))

    from app.llm.schemas import PeriodSummary

    client = LLMClient(
        AnthropicProvider("", client=fake_client(handler)),
        {"extract": "claude-sonnet-5-5", "light": "claude-haiku-5-5"},
        {"light": "low"},
    )
    await client.complete_json(
        "period_summary", "period_summary", {"PERIOD": "day"}, PeriodSummary, "light"
    )
    assert "fallbacks" not in seen["body"] and seen["body"]["output_config"]["effort"] == "low"


@pytest.mark.parametrize(
    "status,body,permanent,text",
    [
        (
            401,
            {
                "type": "error",
                "error": {"type": "authentication_error", "message": "invalid x-api-key"},
            },
            True,
            "401",
        ),
        (
            400,
            {
                "type": "error",
                "error": {
                    "type": "invalid_request_error",
                    "message": "Your credit balance is too low",
                },
            },
            True,
            "credit",
        ),
        (
            404,
            {"type": "error", "error": {"type": "not_found_error", "message": "model"}},
            True,
            "404",
        ),
        (
            529,
            {"type": "error", "error": {"type": "overloaded_error", "message": "Overloaded"}},
            False,
            "529",
        ),
    ],
)
async def test_error_classification(status, body, permanent, text):
    provider = AnthropicProvider(
        "", client=fake_client(lambda req: httpx2.Response(status, json=body))
    )
    with pytest.raises(LLMError) as e:
        await provider.generate(
            purpose="x",
            system="s",
            user="u",
            schema={"type": "object", "properties": {}, "additionalProperties": False},
            model="claude-sonnet-5-5",
            variables={},
        )
    assert e.value.permanent is permanent and text in str(e.value)


async def test_refusal_is_permanent():
    provider = AnthropicProvider(
        "", client=fake_client(lambda req: httpx2.Response(200, json=message("", "refusal")))
    )
    with pytest.raises(LLMError) as e:
        await provider.generate(
            purpose="x", system="s", user="u", schema={}, model="claude-sonnet-5-5", variables={}
        )
    assert e.value.permanent


async def test_permanent_error_fails_job_immediately(make_user, pg):
    body = {
        "type": "error",
        "error": {"type": "authentication_error", "message": "invalid x-api-key"},
    }
    set_llm(
        LLMClient(
            AnthropicProvider("", client=fake_client(lambda req: httpx2.Response(401, json=body))),
            {"extract": "claude-sonnet-5-5", "light": "claude-haiku-5-5"},
        )
    )
    try:
        user = await make_user()
        r = await user.client.post("/entries", json={"entry_date": "2026-11-25", "body": HACKATHON})
        await drain_jobs()
        job = (await user.client.get(f"/jobs/{r.json()['job_id']}")).json()
        assert job["status"] == "failed" and job["attempts"] == 1  # 재시도 대기 없이 바로 실패
        assert "401" in job["last_error"]
        entry = (await user.client.get(f"/entries/{r.json()['entry']['id']}")).json()
        assert entry["extraction_status"] == "failed"
    finally:
        set_llm(None)


async def test_web_search_collects_urls_only_from_result_blocks():
    """검색 결과 블록의 URL만 모은다. 모델이 답변에 쓴 URL은 쓰지 않는다. pause_turn이면 이어 부른다."""
    calls = []

    def search_message(stop_reason, urls, text_url=None):
        content = [
            {
                "type": "server_tool_use",
                "id": f"srv_{len(calls)}",
                "name": "web_search",
                "input": {"query": "q"},
            },
            {
                "type": "web_search_tool_result",
                "tool_use_id": f"srv_{len(calls)}",
                "content": [
                    {
                        "type": "web_search_result",
                        "url": u,
                        "title": "t",
                        "encrypted_content": "x",
                        "page_age": None,
                    }
                    for u in urls
                ],
            },
        ]
        if text_url:
            content.append({"type": "text", "text": f"여기도 있다: {text_url}"})
        return {
            "id": "m",
            "type": "message",
            "role": "assistant",
            "model": "claude-haiku-5-5",
            "content": content,
            "stop_reason": stop_reason,
            "stop_sequence": None,
            "usage": {"input_tokens": 10, "output_tokens": 5},
        }

    def handler(request):
        body = json.loads(request.content)
        calls.append(body)
        assert body["tools"][0]["name"] == "web_search"
        assert "output_config" not in body
        if len(calls) == 1:
            return httpx2.Response(
                200, json=search_message("pause_turn", ["https://a.example.org/1"])
            )
        return httpx2.Response(
            200,
            json=search_message(
                "end_turn",
                ["https://b.example.org/2", "https://a.example.org/1"],
                text_url="https://made-up.example.org/x",
            ),
        )

    provider = AnthropicProvider("k", client=fake_client(handler))
    client = LLMClient(provider, {"extract": "claude-sonnet-5-5", "light": "claude-haiku-5-5"})
    hits = await client.search_web("대학생 해커톤 모집 2026")
    assert [h["url"] for h in hits] == ["https://a.example.org/1", "https://b.example.org/2"]
    assert len(calls) == 2 and calls[1]["messages"][-1]["role"] == "assistant"
