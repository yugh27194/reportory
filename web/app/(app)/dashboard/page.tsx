"use client";

import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  CalendarClock,
  Check,
  ClipboardCheck,
  Compass,
  FileText,
  Flame,
  NotebookPen,
  Quote,
  Sparkles,
  Target,
} from "lucide-react";
import Link from "next/link";
import { useGrowth, useMe } from "@/components/AppShell";
import { ErrorText } from "@/components/ErrorText";
import { OliveTree, STAGE_HINTS } from "@/components/OliveTree";
import { SpecRadar } from "@/components/SpecRadar";
import { MarkdownLite, StatCard, TypeIcon } from "@/components/ui";
import { api } from "@/lib/api";
import { ddayLabel, daysLeft } from "@/lib/dday";
import { questionOfDay } from "@/lib/prompts";
import { CATEGORY_LABELS, type Application, type Stats } from "@/lib/types";

function greeting() {
  const h = new Date().getHours();
  if (h < 6) return "늦은 밤이다";
  if (h < 12) return "좋은 아침이다";
  if (h < 18) return "좋은 오후다";
  return "오늘 하루도 수고했다";
}

type Step = { done: boolean; title: string; desc: string; href: string; cta: string; icon: typeof Target };

function GettingStarted({ steps }: { steps: Step[] }) {
  const done = steps.filter((s) => s.done).length;
  const next = steps.find((s) => !s.done);
  return (
    <section className="card overflow-hidden p-0">
      <div className="flex flex-wrap items-center gap-4 border-b border-line/70 bg-gradient-to-r from-mint/70 to-cream/60 px-5 py-4">
        <div className="mr-auto">
          <p className="section-title">Getting started</p>
          <h2 className="mt-0.5 text-lg font-bold">처음 시작하기</h2>
          <p className="text-sm text-muted">다섯 가지만 해 보면 re:portory가 어떻게 쌓이는지 알 수 있다.</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="h-2 w-36 overflow-hidden rounded-full bg-white">
            <div
              className="h-full rounded-full bg-gradient-to-r from-deep to-accent transition-all"
              style={{ width: `${(done / steps.length) * 100}%` }}
            />
          </div>
          <span className="text-sm font-semibold text-deep">
            {done} / {steps.length}
          </span>
        </div>
      </div>
      <ol className="divide-y divide-line/70">
        {steps.map((s) => {
          const isNext = s === next;
          return (
            <li key={s.title}>
              <Link
                href={s.href}
                className={`flex items-center gap-4 px-5 py-3.5 transition hover:bg-cream/50 ${isNext ? "bg-white" : ""}`}
              >
                <span
                  className={`inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full ${
                    s.done ? "bg-accent text-ink" : isNext ? "bg-ink text-accent" : "bg-cream text-muted"
                  }`}
                >
                  {s.done ? <Check size={17} strokeWidth={3} /> : <s.icon size={17} />}
                </span>
                <span className="min-w-0 flex-1">
                  <span className={`block font-semibold ${s.done ? "text-muted line-through decoration-1" : ""}`}>
                    {s.title}
                  </span>
                  {!s.done && <span className="block text-sm text-muted">{s.desc}</span>}
                </span>
                {!s.done && (
                  <span className={`btn btn-sm shrink-0 ${isNext ? "btn-primary" : ""}`}>
                    {s.cta} <ArrowRight size={13} />
                  </span>
                )}
              </Link>
            </li>
          );
        })}
      </ol>
    </section>
  );
}

function UpcomingDeadlines() {
  const apps = useQuery({
    queryKey: ["applications"],
    queryFn: () => api<{ applications: Application[] }>("/applications"),
  });
  const soon = (apps.data?.applications ?? [])
    .filter(
      (a) =>
        ["interested", "applied"].includes(a.status) && a.apply_deadline && (daysLeft(a.apply_deadline) ?? -1) >= 0,
    )
    .slice(0, 4);
  return (
    <section className="card flex flex-col">
      <div className="mb-3 flex items-center">
        <h2 className="flex items-center gap-2 font-semibold">
          <CalendarClock size={16} className="text-accent-2" /> 다가오는 마감
        </h2>
        <Link href="/applications" className="ml-auto text-sm text-deep hover:underline">
          지원 관리
        </Link>
      </div>
      {soon.length === 0 ? (
        <div className="flex flex-1 flex-col items-start justify-center gap-2 rounded-xl bg-cream/60 p-4 text-sm text-muted">
          <p>챙길 마감이 없다. 나에게 맞는 공모전·대외활동·인턴을 둘러보세요.</p>
          <Link href="/recommendations" className="btn btn-sm">
            <Compass size={14} /> 활동 추천 보기
          </Link>
        </div>
      ) : (
        <ul className="space-y-2">
          {soon.map((a) => {
            const d = daysLeft(a.apply_deadline) ?? 99;
            return (
              <li key={a.id}>
                <Link
                  href={`/applications?open=${a.id}`}
                  className="flex items-center gap-3 rounded-xl border border-line/70 p-3 hover:border-accent/60"
                >
                  <span
                    className={`w-16 shrink-0 rounded-lg py-1 text-center text-xs font-bold ${
                      d <= 3 ? "bg-ink text-accent" : "bg-cream text-ink/80"
                    }`}
                  >
                    {ddayLabel(a.apply_deadline)}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-semibold">{a.title}</span>
                    <span className="text-xs text-muted">
                      {CATEGORY_LABELS[a.category]} · {a.status === "applied" ? "지원함" : "관심"}
                    </span>
                  </span>
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

export default function DashboardPage() {
  const me = useMe();
  const stats = useQuery({ queryKey: ["stats"], queryFn: () => api<Stats>("/me/stats") });
  const growth = useGrowth();
  const s = stats.data;
  const p = me.data?.profile;
  const g = growth.data;
  const pending = (s?.pending_proposals ?? 0) + (s?.open_followups ?? 0);
  const name = p?.display_name ? `${p.display_name}님` : "";

  const steps: Step[] = [
    {
      done: !!p?.onboarding_completed_at || (p?.goal ?? "undecided") !== "undecided",
      title: "목표와 관심 분야 정하기",
      desc: "취업·진학 중 무엇을 준비하는지 알려 주면 문서와 추천이 맞춰진다. 이력서·GitHub도 가져올 수 있다.",
      href: "/onboarding",
      cta: "정하기",
      icon: Target,
    },
    {
      done: (s?.entries.total ?? 0) > 0,
      title: "첫 일기 쓰기",
      desc: "오늘 한 일을 두세 문장만 적어도 된다.",
      href: "/journal",
      cta: "쓰기",
      icon: NotebookPen,
    },
    {
      done: (s?.items_total ?? 0) > 0,
      title: "첫 경험 담기",
      desc: "AI가 일기에서 찾은 경험 후보 중 맞는 것을 '추가'한다.",
      href: pending > 0 ? "/review" : "/journal",
      cta: "담기",
      icon: ClipboardCheck,
    },
    {
      done: (s?.recommendations_seen ?? 0) > 0 || (s?.applications ?? 0) > 0,
      title: "나에게 맞는 활동 찾아보기",
      desc: "추천 공고에 관심이나 숨김을 눌러 보면 다음 추천이 더 정확해진다.",
      href: "/recommendations",
      cta: "둘러보기",
      icon: Compass,
    },
    {
      done: (s?.documents ?? 0) > 0,
      title: "첫 문서 만들기",
      desc: "모은 경험으로 이력서나 포트폴리오를 만들어 본다.",
      href: "/documents/new",
      cta: "만들기",
      icon: FileText,
    },
  ];
  const allDone = steps.every((x) => x.done);
  const fresh = !!s && s.entries.total === 0 && s.items_total === 0;

  return (
    <div className="space-y-6 sm:space-y-8">
      <section className="relative overflow-hidden rounded-3xl bg-ink p-6 text-white sm:p-9">
        <div className="pointer-events-none absolute -top-24 -right-24 h-72 w-72 rounded-full bg-deep blur-3xl" />
        <div className="pointer-events-none absolute right-6 -bottom-6 hidden w-40 opacity-90 sm:block">
          <OliveTree level={g?.stage.level ?? 0} sway />
        </div>
        <div className="relative max-w-xl">
          <p className="text-sm text-accent">
            {greeting()}
            {name && `, ${name}`}
          </p>
          {s?.wrote_today ? (
            <>
              <h1 className="mt-1 text-2xl font-bold sm:text-3xl">오늘도 기록을 남겼다.</h1>
              <p className="mt-2 text-white/70">
                {s.streak > 1 ? `${s.streak}일째 이어서 쓰고 있다. ` : ""}
                {pending > 0 ? `일기에서 찾은 경험 후보 ${pending}개가 기다리고 있다.` : "내일도 한두 줄이면 충분하다."}
              </p>
            </>
          ) : (
            <>
              <h1 className="mt-1 text-2xl leading-snug font-bold sm:text-3xl">{questionOfDay()}</h1>
              <p className="mt-2 text-white/60">
                {s && s.streak > 0
                  ? `어제까지 ${s.streak}일 이어서 썼다. 오늘 쓰면 ${s.streak + 1}일째가 된다.`
                  : "떠오르는 대로 두세 문장만 적으면, 경험을 찾아 정리하는 건 re:portory가 한다."}
              </p>
            </>
          )}
          <div className="mt-5 flex flex-wrap gap-2">
            <Link href="/journal" className="btn btn-accent">
              <NotebookPen size={16} /> {s?.wrote_today ? "더 쓰기" : "오늘 기록하기"}
            </Link>
            {pending > 0 && (
              <Link
                href="/review"
                className="btn border-white/20 bg-white/10 text-white hover:bg-white/20 hover:text-white"
              >
                <ClipboardCheck size={16} /> 확인할 항목 {pending}개
              </Link>
            )}
          </div>
        </div>
      </section>

      {s && !allDone && <GettingStarted steps={steps} />}

      {!fresh && (
        <section className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
          <StatCard label="모은 경험" value={s?.items_total ?? "–"} hint="승인한 항목" href="/portfolio" tone="ink" />
          <StatCard
            label="연속 기록"
            value={
              <span className="inline-flex items-center gap-1.5">
                <Flame size={22} className={s?.wrote_today ? "text-accent-2" : "text-muted"} />
                {s?.streak ?? 0}일
              </span>
            }
            hint={s?.wrote_today ? "오늘도 썼다" : "오늘 쓰면 이어진다"}
            href="/journal"
            tone="mint"
          />
          <StatCard
            label="이번 주 일기"
            value={s?.entries.this_week ?? "–"}
            hint={`전체 ${s?.entries.total ?? 0}편`}
            href="/journal"
          />
          <StatCard label="문서" value={s?.documents ?? "–"} hint={`증빙 ${s?.evidence ?? 0}개`} href="/documents" />
        </section>
      )}

      <div className="grid gap-6 lg:grid-cols-[1.6fr_1fr]">
        <section className="card grid gap-4 sm:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]" data-tour="growth">
          <Link
            href="/portfolio"
            className="group relative flex flex-col items-center rounded-2xl bg-gradient-to-b from-mint/60 to-cream/50 p-3"
          >
            <OliveTree
              level={g?.stage.level ?? 0}
              className="h-56 w-full transition group-hover:scale-[1.03]"
              title={g?.stage.label}
            />
            <p className="mt-1 font-semibold">{g?.stage.label ?? "화분"}</p>
            <p className="text-center text-xs text-muted">{STAGE_HINTS[g?.stage.level ?? 0]}</p>
            {g && g.stage.next_at !== null && (
              <div className="mt-2 w-full max-w-48">
                <div className="h-1.5 overflow-hidden rounded-full bg-white">
                  <div
                    className="h-full rounded-full bg-gradient-to-r from-deep to-accent"
                    style={{ width: `${Math.round(g.stage.progress * 100)}%` }}
                  />
                </div>
                <p className="mt-1 text-center text-[11px] text-muted">
                  다음 단계까지 {g.stage.next_at - g.stage.score}점 · 경험 1개 2점, 기록한 날 1점
                </p>
              </div>
            )}
            <span className="mt-2 text-xs font-medium text-deep group-hover:underline">나무 들여다보기 →</span>
          </Link>
          <div>
            <h2 className="mb-1 font-semibold">스펙 레이더</h2>
            <p className="mb-2 text-xs text-muted">주홍 선은 목표 기준선, 파란 면은 지금 모은 경험이다.</p>
            {g && <SpecRadar growth={g} />}
          </div>
        </section>

        <div className="space-y-6">
          <UpcomingDeadlines />
          <section className="card flex flex-col">
            <div className="mb-3 flex items-center">
              <h2 className="flex items-center gap-2 font-semibold">
                <Sparkles size={16} className="text-accent-2" /> 최근 돌아보기
              </h2>
              <Link href="/summaries" className="ml-auto text-sm text-deep hover:underline">
                모두 보기
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
              <p className="flex gap-2 rounded-xl bg-cream/60 p-4 text-sm text-muted">
                <Quote size={15} className="mt-0.5 shrink-0 text-deep" />
                일기를 쓰면 그날 밤, 일요일 밤, 월 마지막 날 밤에 기록을 돌아보는 요약이 도착한다.
              </p>
            )}
          </section>
        </div>
      </div>

      {!!s?.recent_items.length && (
        <section className="card">
          <div className="mb-4 flex items-center">
            <h2 className="font-semibold">최근 담은 경험</h2>
            <Link
              href="/documents/new"
              className="ml-auto inline-flex items-center gap-1 text-sm text-deep hover:underline"
            >
              <FileText size={14} /> 문서 만들기
            </Link>
          </div>
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
        </section>
      )}
      <ErrorText error={stats.error} />
    </div>
  );
}
