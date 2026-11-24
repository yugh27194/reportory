"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowRight, ClipboardCheck, FileText, NotebookPen, Rocket, Sparkles } from "lucide-react";
import Link from "next/link";
import { useMe } from "@/components/AppShell";
import { ErrorText } from "@/components/ErrorText";
import { MarkdownLite, StatCard, TypeIcon } from "@/components/ui";
import { api } from "@/lib/api";
import { ITEM_TYPE_LABELS, ITEM_TYPE_ORDER, type Stats } from "@/lib/types";

function greeting() {
  const h = new Date().getHours();
  if (h < 6) return "늦은 밤이다";
  if (h < 12) return "좋은 아침이다";
  if (h < 18) return "좋은 오후다";
  return "오늘 하루도 수고했다";
}

export default function DashboardPage() {
  const me = useMe();
  const stats = useQuery({ queryKey: ["stats"], queryFn: () => api<Stats>("/me/stats") });
  const s = stats.data;
  const p = me.data?.profile;
  const pending = (s?.pending_proposals ?? 0) + (s?.open_followups ?? 0);
  const maxType = Math.max(1, ...Object.values(s?.items_by_type ?? {}).map((n) => n ?? 0));

  return (
    <div className="space-y-8">
      <section className="relative overflow-hidden rounded-3xl bg-ink p-7 text-white sm:p-9">
        <div className="pointer-events-none absolute -top-24 -right-24 h-72 w-72 rounded-full bg-deep blur-3xl" />
        <div className="relative flex flex-wrap items-end gap-6">
          <div className="mr-auto">
            <p className="text-sm text-accent">{greeting()}</p>
            <h1 className="mt-1 text-2xl font-bold sm:text-3xl">
              {p?.display_name ? `${p.display_name}님의 기록` : "나의 기록"}
            </h1>
            <p className="mt-2 text-white/60">
              최근 30일 동안 {s?.entries.days_this_month ?? 0}일 기록했다. 항목은 모두 {s?.items_total ?? 0}개다.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Link href="/journal" className="btn btn-accent">
              <NotebookPen size={16} /> 일기 쓰기
            </Link>
            {pending > 0 && (
              <Link href="/review" className="btn border-white/20 bg-white/10 text-white hover:bg-white/20 hover:text-white">
                <ClipboardCheck size={16} /> 확인할 항목 {pending}개
              </Link>
            )}
          </div>
        </div>
      </section>

      {p && !p.onboarding_completed_at && (
        <Link
          href="/onboarding"
          className="card card-hover flex items-center gap-4 border-accent/50 bg-mint/60"
        >
          <span className="inline-flex h-11 w-11 items-center justify-center rounded-2xl bg-deep text-mint">
            <Rocket size={20} />
          </span>
          <div className="min-w-0 flex-1">
            <p className="font-semibold">처음 설정을 마쳐 보세요</p>
            <p className="text-sm text-muted">목표를 정하고 이력서·GitHub·LinkedIn에서 기록을 가져오면 바로 포트폴리오가 채워진다.</p>
          </div>
          <ArrowRight className="text-deep" />
        </Link>
      )}

      <section className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
        <StatCard label="포트폴리오 항목" value={s?.items_total ?? "–"} hint="승인한 항목" href="/portfolio" tone="ink" />
        <StatCard label="확인할 항목" value={pending} hint="고르지 않은 경험 후보" href="/review" tone="mint" />
        <StatCard label="이번 주 일기" value={s?.entries.this_week ?? "–"} hint={`전체 ${s?.entries.total ?? 0}편`} href="/journal" />
        <StatCard label="문서" value={s?.documents ?? "–"} hint={`증빙 ${s?.evidence ?? 0}개`} href="/documents" />
      </section>

      <div className="grid gap-6 lg:grid-cols-[1.3fr_1fr]">
        <section className="card">
          <div className="mb-4 flex items-center">
            <h2 className="font-semibold">유형별 항목</h2>
            <Link href="/portfolio" className="ml-auto text-sm text-deep hover:underline">
              전체 보기
            </Link>
          </div>
          {s && s.items_total === 0 ? (
            <p className="text-sm text-muted">아직 승인한 항목이 없다. 일기를 쓰거나 이력서를 가져와 보세요.</p>
          ) : (
            <ul className="space-y-3">
              {ITEM_TYPE_ORDER.map((t) => {
                const n = s?.items_by_type[t] ?? 0;
                return (
                  <li key={t} className="flex items-center gap-3">
                    <TypeIcon type={t} size="sm" />
                    <span className="w-16 text-sm">{ITEM_TYPE_LABELS[t]}</span>
                    <span className="h-2 flex-1 overflow-hidden rounded-full bg-cream">
                      <span
                        className="block h-full rounded-full bg-gradient-to-r from-deep to-accent"
                        style={{ width: `${(n / maxType) * 100}%` }}
                      />
                    </span>
                    <span className="w-6 text-right text-sm font-semibold">{n}</span>
                  </li>
                );
              })}
            </ul>
          )}
        </section>

        <section className="card flex flex-col">
          <div className="mb-3 flex items-center">
            <h2 className="flex items-center gap-2 font-semibold">
              <Sparkles size={16} className="text-accent-2" /> 최근 요약
            </h2>
            <Link href="/summaries" className="ml-auto text-sm text-deep hover:underline">
              모든 요약
            </Link>
          </div>
          {s?.latest_summary ? (
            <>
              <p className="mb-2 text-xs text-muted">
                {s.latest_summary.period_start} ~ {s.latest_summary.period_end}
              </p>
              <MarkdownLite text={s.latest_summary.summary_md} />
            </>
          ) : (
            <p className="text-sm text-muted">
              일기를 쓰면 그날 밤, 일요일 밤, 월 마지막 날 밤에 기록을 돌아보는 요약이 만들어진다.
            </p>
          )}
        </section>
      </div>

      <section className="card">
        <div className="mb-4 flex items-center">
          <h2 className="font-semibold">최근 승인한 항목</h2>
          <Link href="/documents/new" className="ml-auto inline-flex items-center gap-1 text-sm text-deep hover:underline">
            <FileText size={14} /> 문서 만들기
          </Link>
        </div>
        {s?.recent_items.length ? (
          <ul className="divide-y divide-line/70">
            {s.recent_items.map((i) => (
              <li key={i.id}>
                <Link href={`/portfolio/${i.id}`} className="flex items-center gap-3 py-3 hover:text-deep">
                  <TypeIcon type={i.type} size="sm" />
                  <span className="min-w-0 flex-1 truncate font-medium">{i.title}</span>
                  <span className="text-xs text-muted">{i.organization}</span>
                </Link>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted">승인한 항목이 여기에 보인다.</p>
        )}
      </section>
      <ErrorText error={stats.error} />
    </div>
  );
}
