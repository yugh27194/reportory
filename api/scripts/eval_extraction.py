"""골든 일기로 실제 모델의 추출 품질을 잰다(인계서 16장). 단위 테스트와 달리 실제 LLM API를 부른다.

실행: `cd api && uv run python scripts/eval_extraction.py` (ANTHROPIC_API_KEY 필요)
프롬프트를 바꿀 때마다 돌리고 결과를 docs/decisions.md에 남긴다. Phase 1 완료 기준은 10개 중 8개 이상이다.
"""

import asyncio
import json
import re
import sys
from datetime import date
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.llm.client import get_llm, load_prompt  # noqa: E402
from app.llm.schemas import ExtractionResult  # noqa: E402
from app.llm.validators import validate_extraction  # noqa: E402

FIXTURES = Path(__file__).resolve().parents[1] / "tests/fixtures/diaries"


def check(case: dict, result: ExtractionResult) -> list[str]:
    exp, fails = case["expect"], []
    if "is_relevant" in exp and result.is_relevant != exp["is_relevant"]:
        fails.append(f"is_relevant={result.is_relevant}")
    for want in exp.get("candidates", []):
        match = [
            c
            for c in result.items
            if c.action == want["action"]
            and ("type" not in want or c.type == want["type"])
            and ("target_item_id" not in want or str(c.target_item_id) == want["target_item_id"])
        ]
        if not match:
            fails.append(f"후보 없음: {want}")
            continue
        c = match[0]
        for s in want.get("skills_include", []):
            if s.lower() not in [x.lower() for x in c.skills]:
                fails.append(f"기술 누락: {s}")
        for v in want.get("metrics_include", []):
            if v not in [m.value for m in c.metrics]:
                fails.append(f"수치 누락: {v}")
        for k, v in want.get("details", {}).items():
            if c.details.get(k) != v:
                fails.append(f"details.{k}={c.details.get(k)!r}")
    if exp.get("no_create") and any(c.action == "create" for c in result.items):
        fails.append("create가 나오면 안 된다")
    for want in exp.get("application_updates", []):
        if not any(
            str(u.application_id) == want["application_id"] and u.to_status == want["to_status"]
            for u in result.application_updates
        ):
            fails.append(f"지원 결과 없음: {want}")
    if "allowed_types" in exp:
        bad = [c.type for c in result.items if c.type not in exp["allowed_types"]]
        if bad:
            fails.append(f"허용되지 않은 유형: {bad}")
    for c in result.items:
        for k in exp.get("forbidden_details", []):
            if c.details.get(k):
                fails.append(f"만들어 낸 값: details.{k}")
        dump = json.dumps(c.model_dump(mode="json"), ensure_ascii=False)
        nums = set(re.findall(r"\d+(?:\.\d+)?", json.dumps([m.value for m in c.metrics])))
        if exp.get("forbidden_numbers_any") and nums:
            fails.append(f"만들어 낸 수치: {nums}")
        for n in exp.get("forbidden_numbers", []):
            if n in nums:
                fails.append(f"만들어 낸 수치 {n}: {dump[:80]}")
    return fails


async def main() -> int:
    llm = get_llm()
    prompt = load_prompt("extract_entry")
    passed, rows = 0, []
    cases = sorted(FIXTURES.glob("*.json"))
    for path in cases:
        case = json.loads(path.read_text())
        raw = await llm.complete_json(
            "eval_extraction",
            "extract_entry",
            {
                "ENTRY_DATE": case["entry_date"],
                "ENTRY": case["entry"],
                "KNOWN_ITEMS": case["known_items"],
                "OPEN_APPLICATIONS": case["open_applications"],
            },
            ExtractionResult,
            "extract",
        )
        result, _, _ = validate_extraction(
            raw,
            case["entry"],
            date.fromisoformat(case["entry_date"]),
            {UUID(i["id"]) for i in case["known_items"]},
            {UUID(a["id"]) for a in case["open_applications"]},
        )
        fails = check(case, result)
        passed += not fails
        rows.append((path.stem, "통과" if not fails else "; ".join(fails)))
    print(f"prompt extract_entry@{prompt.version}, model {llm.models['extract']}")
    for name, status in rows:
        print(f"- {name}: {status}")
    print(f"결과: {passed}/{len(cases)}")
    return 0 if passed >= 0.8 * len(cases) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
