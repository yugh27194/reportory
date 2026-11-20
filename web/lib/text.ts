export type Segment = { text: string; highlight: boolean };

/**
 * 원문에서 인용 구간을 찾아 강조 구간으로 나눈다. 서버 검증과 같이 공백 차이는 무시한다.
 * 찾지 못하면 원문 전체를 강조 없이 돌려준다.
 */
export function highlightQuote(body: string, quote: string | null | undefined): Segment[] {
  const q = (quote ?? "").trim().split(/\s+/).filter(Boolean);
  if (!q.length) return [{ text: body, highlight: false }];
  const escaped = q.map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  const match = new RegExp(escaped.join("\\s+")).exec(body);
  if (!match) return [{ text: body, highlight: false }];
  const start = match.index;
  const end = start + match[0].length;
  return [
    { text: body.slice(0, start), highlight: false },
    { text: body.slice(start, end), highlight: true },
    { text: body.slice(end), highlight: false },
  ].filter((s) => s.text.length > 0);
}

/** 기간 표시: "2026.03 – 2026.06", 진행 중이면 "2026.03 – 진행 중". */
export function formatPeriod(start: string | null, end: string | null, ongoing: boolean): string {
  const fmt = (d: string) => d.slice(0, 7).replace("-", ".");
  if (!start && !end) return ongoing ? "진행 중" : "";
  const left = start ? fmt(start) : "";
  const right = ongoing ? "진행 중" : end ? fmt(end) : "";
  if (left && right && left !== right) return `${left} – ${right}`;
  return left || right;
}

export function todayKST(): string {
  return new Intl.DateTimeFormat("sv-SE", { timeZone: "Asia/Seoul" }).format(new Date());
}
