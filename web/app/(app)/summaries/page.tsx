"use client";

import { useQuery } from "@tanstack/react-query";
import { Sparkles } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { ErrorText } from "@/components/ErrorText";
import { EmptyState, MarkdownLite, PageHeader, Tabs } from "@/components/ui";
import { api } from "@/lib/api";
import type { PeriodSummary } from "@/lib/types";

function rangeLabel(s: PeriodSummary) {
  const a = new Date(s.period_start);
  const b = new Date(s.period_end);
  if (s.period === "month") return `${a.getFullYear()}년 ${a.getMonth() + 1}월`;
  if (s.period === "day") return `${a.getMonth() + 1}월 ${a.getDate()}일 ${"일월화수목금토"[a.getDay()]}요일`;
  return `${a.getMonth() + 1}월 ${a.getDate()}일 ~ ${b.getMonth() + 1}월 ${b.getDate()}일`;
}

export default function SummariesPage() {
  const [period, setPeriod] = useState<"day" | "week" | "month">("day");
  const list = useQuery({
    queryKey: ["summaries", period],
    queryFn: () => api<{ summaries: PeriodSummary[] }>(`/summaries?period=${period}`),
  });
  return (
    <div>
      <PageHeader
        eyebrow="Summaries"
        title="기록 요약"
        description="하루 요약은 매일 밤, 주간 요약은 일요일 밤, 월간 요약은 그달 마지막 날 밤에 만들어진다."
        actions={
          <Tabs
            value={period}
            onChange={setPeriod}
            tabs={[
              { key: "day", label: "일간" },
              { key: "week", label: "주간" },
              { key: "month", label: "월간" },
            ]}
          />
        }
      />
      <ErrorText error={list.error} />
      {list.isSuccess && list.data.summaries.length === 0 && (
        <EmptyState
          icon={Sparkles}
          title="아직 도착한 요약이 없다"
          description="일기를 쓰면 그날 밤에 하루 요약, 일요일 밤에 한 주 요약, 월 마지막 날 밤에 한 달 요약이 이곳에 도착한다."
          action={
            <Link href="/journal" className="btn btn-primary">
              오늘 기록하기
            </Link>
          }
        />
      )}
      <ol className="relative space-y-6 border-l-2 border-mint pl-6">
        {list.data?.summaries.map((s) => (
          <li key={s.id} className="relative">
            <span className="absolute top-5 -left-[33px] h-4 w-4 rounded-full border-4 border-paper bg-accent" />
            <article className="card">
              <p className="section-title">{rangeLabel(s)}</p>
              <div className="mt-3">
                <MarkdownLite text={s.summary_md} />
              </div>
              {s.highlights.length > 0 && (
                <div className="mt-4 flex flex-wrap gap-2 border-t border-line/70 pt-4">
                  {s.highlights.map((h) => (
                    <Link key={h.item_id} href={`/portfolio/${h.item_id}`} className="chip hover:bg-accent/30">
                      ★ {h.text}
                    </Link>
                  ))}
                </div>
              )}
            </article>
          </li>
        ))}
      </ol>
    </div>
  );
}
