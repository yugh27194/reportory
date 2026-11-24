"""LLM에 보내는 JSON 스키마 만들기(구조화 출력 `output_config.format`).

Claude 구조화 출력은 모든 객체에 `additionalProperties: false`가 필요하고 숫자·문자열 길이 제약을
받지 않는다. Pydantic 스키마에서 그런 제약을 지우고(검증은 응답을 받은 뒤 Pydantic으로 한다),
자유 형식 객체인 `details`는 유형별 details 키(10.2절)를 모두 나열한 객체로 바꾼다.
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
        "type": "object",
        "description": "유형에 맞는 키만 채운다. 원문에 없으면 null이다.",
        "properties": {
            k: {"anyOf": [{"type": "string"}, {"type": "integer"}, {"type": "null"}]} for k in keys
        },
        "additionalProperties": False,
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
    """구조화 출력이 채운 null details 키를 지운다(정해진 키 중 값이 있는 것만 남긴다)."""
    if isinstance(data, dict):
        return {
            k: (
                drop_nulls(v)
                if k not in FREE_FORM_KEYS
                else {dk: dv for dk, dv in (v or {}).items() if dv is not None}
            )
            for k, v in data.items()
        }
    if isinstance(data, list):
        return [drop_nulls(x) for x in data]
    return data
