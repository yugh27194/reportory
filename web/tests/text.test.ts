import { describe, expect, it } from "vitest";
import { formatPeriod, highlightQuote } from "@/lib/text";

describe("highlightQuote", () => {
  const body = "오늘 해커톤에서 팀원 3명과\nFastAPI로 백엔드를 맡았다.";

  it("공백 차이를 무시하고 인용 구간을 강조한다", () => {
    const segs = highlightQuote(body, "팀원 3명과 FastAPI로");
    expect(segs).toEqual([
      { text: "오늘 해커톤에서 ", highlight: false },
      { text: "팀원 3명과\nFastAPI로", highlight: true },
      { text: " 백엔드를 맡았다.", highlight: false },
    ]);
  });

  it("인용을 찾지 못하면 원문을 그대로 돌려준다", () => {
    expect(highlightQuote(body, "없는 문장")).toEqual([{ text: body, highlight: false }]);
    expect(highlightQuote(body, null)).toEqual([{ text: body, highlight: false }]);
  });

  it("정규식 특수문자가 든 인용도 찾는다", () => {
    const segs = highlightQuote("정확도(0.78)를 얻었다", "정확도(0.78)");
    expect(segs[0]).toEqual({ text: "정확도(0.78)", highlight: true });
  });
});

describe("formatPeriod", () => {
  it("기간을 연.월로 보여 준다", () => {
    expect(formatPeriod("2026-03-01", "2026-06-30", false)).toBe("2026.03 – 2026.06");
    expect(formatPeriod("2026-03-01", null, true)).toBe("2026.03 – 진행 중");
    expect(formatPeriod("2026-03-01", "2026-03-20", false)).toBe("2026.03");
    expect(formatPeriod(null, null, false)).toBe("");
  });
});
