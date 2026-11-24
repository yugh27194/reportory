import { afterEach, describe, expect, it, vi } from "vitest";
import { daysLeft, ddayLabel } from "@/lib/dday";

describe("dday", () => {
  afterEach(() => vi.useRealTimers());

  it("한국 날짜 기준으로 남은 날을 센다", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-11-24T16:00:00Z")); // 한국 11월 25일 01:00
    expect(daysLeft("2026-11-25")).toBe(0);
    expect(ddayLabel("2026-11-25")).toBe("오늘 마감");
    expect(ddayLabel("2026-11-30")).toBe("D-5");
    expect(ddayLabel("2026-11-24")).toBe("마감");
    expect(ddayLabel(null)).toBe("상시");
  });
});
