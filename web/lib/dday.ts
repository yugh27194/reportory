import { todayKST } from "@/lib/text";

/** 마감까지 남은 날(오늘 0). 날짜가 없으면 null. */
export function daysLeft(date: string | null): number | null {
  if (!date) return null;
  const a = new Date(`${todayKST()}T00:00:00Z`).getTime();
  const b = new Date(`${date}T00:00:00Z`).getTime();
  return Math.round((b - a) / 86_400_000);
}

export function ddayLabel(date: string | null): string {
  const d = daysLeft(date);
  if (d === null) return "상시";
  if (d < 0) return "마감";
  if (d === 0) return "오늘 마감";
  return `D-${d}`;
}
