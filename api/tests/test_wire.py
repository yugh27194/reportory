"""구조화 출력 스키마가 API 한도 안에 드는지 확인한다.

선택 속성·유니언이 많으면 Anthropic API가 'compiled grammar is too large'(400)로 거절한다.
"""

import inspect

from pydantic import BaseModel

from app.llm import schemas
from app.llm.wire import drop_nulls, output_schema


def _count(node, acc):
    if isinstance(node, dict):
        if "properties" in node:
            acc["optional"] += len(set(node["properties"]) - set(node.get("required", [])))
            assert node.get("additionalProperties") is False
        if "anyOf" in node:
            acc["unions"] += 1
        for v in node.values():
            _count(v, acc)
    elif isinstance(node, list):
        for v in node:
            _count(v, acc)
    return acc


def test_all_llm_schemas_fit_grammar_limits():
    models = [
        m
        for _, m in inspect.getmembers(schemas, inspect.isclass)
        if issubclass(m, BaseModel) and m is not BaseModel and m.__module__ == schemas.__name__
    ]
    assert models
    for m in models:
        acc = _count(output_schema(m), {"optional": 0, "unions": 0})
        assert acc["optional"] == 0, m.__name__
        assert acc["unions"] <= 12, (m.__name__, acc)


def test_details_pairs_round_trip():
    s = output_schema(schemas.ExtractionResult)
    assert '"details"' in str(s).replace("'", '"')
    out = drop_nulls(
        {
            "candidates": [
                {
                    "title": "x",
                    "summary": None,
                    "details": [
                        {"key": "rank", "value": "3위"},
                        {"key": "host", "value": ""},
                    ],
                }
            ]
        }
    )
    assert out["candidates"][0]["details"] == {"rank": "3위"}
