"""LLM에 보내는 JSON 스키마 만들기(구조화 출력 `output_config.format`).

Claude 구조화 출력은 모든 객체에 `additionalProperties: false`가 필요하고 숫자·문자열 길이 제약을
받지 않는다. Pydantic 스키마에서 그런 제약을 지우고(검증은 응답을 받은 뒤 Pydantic으로 한다),
자유 형식 객체인 `details`는 {key, value} 쌍의 목록으로 보낸다.

선택(optional) 속성과 유니언이 많으면 API가 "compiled grammar is too large"(400)로 거절한다.
그래서 모든 속성을 필수로 만들고(없으면 null), details는 키를 하나하나 나열하지 않고 쌍 목록으로 받는다.
응답은 `drop_nulls`가 다시 Pydantic 모델 모양({key: value})으로 되돌린다.
"""

import copy
from typing import Any

from pydantic import BaseModel

from app.llm.schemas import DETAILS_KEYS

UNSUPPORTED = (
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "exclusiveMaximum",
    "multipleOf",
    "minLength",
    "maxLength",
    "minItems",
    "maxItems",
    "pattern",
    "default",
)
FREE_FORM_KEYS = ("details", "details_patch")


def _details_schema() -> dict:
    keys = sorted({k for keys in DETAILS_KEYS.values() for k in keys})
    return {
        "type": "array",
        "description": "유형에 맞는 세부 정보만 쌍으로 넣는다. 원문에 없는 키는 넣지 않는다.",
        "items": {
            "type": "object",
            "properties": {
                "key": {"type": "string", "enum": keys},
                "value": {"type": "string"},
            },
            "required": ["key", "value"],
            "additionalProperties": False,
        },
    }


def _fix(node: Any, key: str | None = None) -> Any:
    if isinstance(node, list):
        return [_fix(x) for x in node]
    if not isinstance(node, dict):
        return node
    for k in UNSUPPORTED:
        node.pop(k, None)
    is_object = node.get("type") == "object" or "properties" in node
    if is_object and "properties" not in node:
        if key in FREE_FORM_KEYS:
            return _details_schema()
        node = {**node, "properties": {}}
    if is_object:
        node["additionalProperties"] = False
        # 선택 속성은 문법을 크게 키운다. 모두 필수로 두고, 없는 값은 null(또는 빈 목록)로 받는다.
        node["required"] = list(node.get("properties", {}))
    out = {}
    for k, v in node.items():
        if k == "properties":
            out[k] = {pk: _fix(pv, pk) for pk, pv in v.items()}
        elif k in ("$defs", "definitions"):
            out[k] = {dk: _fix(dv) for dk, dv in v.items()}
        else:
            out[k] = _fix(v, key if k in ("anyOf", "allOf", "items") else None)
    return out


def output_schema(model: type[BaseModel]) -> dict:
    return _fix(copy.deepcopy(model.model_json_schema()))


def drop_nulls(data: Any) -> Any:
    """응답을 Pydantic 모델 모양으로 되돌린다: details 쌍 목록 → {key: value}, 빈 값은 버린다."""
    if isinstance(data, dict):
        return {
            k: (drop_nulls(v) if k not in FREE_FORM_KEYS else _pairs_to_dict(v))
            for k, v in data.items()
        }
    if isinstance(data, list):
        return [drop_nulls(x) for x in data]
    return data


def _pairs_to_dict(value: Any) -> dict:
    if isinstance(value, dict):
        return {k: v for k, v in value.items() if v not in (None, "")}
    out: dict = {}
    for pair in value or []:
        if isinstance(pair, dict) and pair.get("key") and pair.get("value") not in (None, ""):
            out[str(pair["key"])] = pair["value"]
    return out
