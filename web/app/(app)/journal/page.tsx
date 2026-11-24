"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  BookOpen,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Leaf,
  NotebookPen,
  Pencil,
  RefreshCw,
  ShieldCheck,
  Trash2,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { ErrorText } from "@/components/ErrorText";
import { EntryReview } from "@/components/InlineReview";
import { PageHeader, Spinner } from "@/components/ui";
import { api, patch, post } from "@/lib/api";
import { todayKST } from "@/lib/text";
import type { Entry, Job, JournalCalendar, Profile, ProposalKind } from "@/lib/types";

type EntryDetail = Entry & {
  proposals: { id: string; kind: ProposalKind; status: string; quote: string | null }[];
  sources: { id: string; item_id: string; item_title: string; item_status: string; quote: string }[];
  job: { id: string; status: Job["status"]; attempts: number; last_error: string | null; run_after: string } | null;
};

const PROMPTS = [
  "오늘 무엇을 만들었나요?",
  "새로 배운 기술이 있나요?",
  "팀에서 맡은 역할은?",
  "결과나 수치가 나왔나요?",
];

function ExtractionStatus({ entry }: { entry: Entry }) {
  const qc = useQueryClient();
  const detail = useQuery({
    queryKey: ["entry", entry.id],
    queryFn: () => api<EntryDetail>(`/entries/${entry.id}`),
    refetchInterval: (q) => {
      const s = q.state.data?.extraction_status;
      return s === "queued" || s === "running" ? 2000 : false;
    },
  });
  const job = useQuery({
    queryKey: ["job", detail.data?.job?.id],
    queryFn: () => api<Job>(`/jobs/${detail.data!.job!.id}`),
    enabled: detail.data?.extraction_status === "succeeded" && !!detail.data?.job,
  });
  const reextract = useMutation({
    mutationFn: () => post(`/entries/${entry.id}/reextract`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["entry", entry.id] });
      qc.invalidateQueries({ queryKey: ["pending-count"] });
    },
  });
  const status = detail.data?.extraction_status;
  useEffect(() => {
    if (status === "succeeded") {
      qc.invalidateQueries({ queryKey: ["pending-count"] });
      qc.invalidateQueries({ queryKey: ["proposals"] });
      qc.invalidateQueries({ queryKey: ["stats"] });
    }
  }, [status, qc]);
  const d = detail.data;
  if (!d) return null;
  const linked = d.sources.filter((s) => s.item_status === "approved");

  return (
    <div className="mt-4 space-y-3 border-t border-line/70 pt-4 text-sm">
      {(status === "queued" || status === "running") &&
        (d.job && d.job.status === "queued" && d.job.attempts > 0 ? (
          <p className="text-amber-800">
            일시적인 오류로{" "}
            {new Date(d.job.run_after).toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit" })}에 다시
            시도한다. ({d.job.last_error})
          </p>
        ) : (
          <Spinner label="기록을 분석하고 있다. 보통 10~30초 걸린다." />
        ))}
      {status === "failed" && (
        <p className="text-red-700">
          분석에 실패했다{d.job?.last_error ? `: ${d.job.last_error}` : "."} 원인을 고친 뒤 다시 분석을 눌러 보세요.
        </p>
      )}
      {status === null && <p className="text-muted">외부 LLM 처리에 동의하면 이 일기를 분석할 수 있다.</p>}
      {status === "succeeded" && job.data?.result && (
        <p className="flex flex-wrap items-center gap-2">
          <CheckCircle2 size={16} className="text-accent-2" />
          {Number(job.data.result.proposals ?? 0) > 0
            ? "분석을 마쳤다."
            : "이 일기에서는 새로 추가할 경험을 찾지 못했다."}
        </p>
      )}
      <EntryReview entryId={entry.id} />
      {linked.length > 0 && (
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs text-muted">연결된 항목</span>
          {linked.map((s) => (
            <Link key={s.id} href={`/portfolio/${s.item_id}`} className="chip chip-cream hover:bg-mint">
              {s.item_title}
            </Link>
          ))}
        </div>
      )}
      {status !== "queued" && status !== "running" && (
        <button className="btn btn-sm" onClick={() => reextract.mutate()} disabled={reextract.isPending}>
          <RefreshCw size={14} /> 다시 분석
        </button>
      )}
      <ErrorText error={reextract.error} />
    </div>
  );
}

function EntryCard({ entry }: { entry: Entry }) {
  const qc = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [body, setBody] = useState(entry.body);
  const save = useMutation({
    mutationFn: () => patch(`/entries/${entry.id}`, { body }),
    onSuccess: () => {
      setEditing(false);
      qc.invalidateQueries({ queryKey: ["entries"] });
    },
  });
  const remove = useMutation({
    mutationFn: () => api(`/entries/${entry.id}`, { method: "DELETE" }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["entries"] });
      qc.invalidateQueries({ queryKey: ["calendar"] });
      qc.invalidateQueries({ queryKey: ["growth"] });
      qc.invalidateQueries({ queryKey: ["pending-count"] });
    },
  });
  const time = new Date(entry.created_at).toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit" });

  return (
    <article className="rounded-xl border border-line/70 bg-white/80 p-4" data-tour="review-help">
      <div className="mb-2 flex items-center gap-2 text-xs text-muted">
        <span>{time}에 씀</span>
        {!editing && (
          <span className="ml-auto flex gap-1">
            <button className="btn-ghost rounded-md p-1.5" onClick={() => setEditing(true)} aria-label="수정">
              <Pencil size={14} />
            </button>
            <button
              className="btn-ghost rounded-md p-1.5 hover:text-red-700"
              aria-label="삭제"
              onClick={() => {
                if (confirm("이 일기를 지운다. 승인한 항목은 남고 근거 연결만 사라진다. 계속할까요?")) remove.mutate();
              }}
            >
              <Trash2 size={14} />
            </button>
          </span>
        )}
      </div>
      {editing ? (
        <>
          <textarea className="input min-h-32" value={body} onChange={(e) => setBody(e.target.value)} />
          <p className="mt-1 text-xs text-muted">
            수정만으로는 다시 분석하지 않는다. 필요하면 저장한 뒤 다시 분석을 누른다.
          </p>
          <div className="mt-2 flex gap-2">
            <button className="btn btn-primary btn-sm" onClick={() => save.mutate()} disabled={save.isPending}>
              저장
            </button>
            <button className="btn btn-sm" onClick={() => setEditing(false)}>
              취소
            </button>
          </div>
        </>
      ) : (
        <p className="text-[15px] leading-relaxed whitespace-pre-wrap">{entry.body}</p>
      )}
      <ExtractionStatus entry={entry} />
      <ErrorText error={save.error ?? remove.error} />
    </article>
  );
}

/** 튜토리얼 '예시로 써 보기'가 채우는 일기. 실제 데이터가 아니라 연습용이라고 밝힌다. */
const SAMPLE_ENTRY =
  "오늘 데이터분석 동아리 스터디에서 Python과 pandas로 학교 식당 이용 데이터를 정리했다. " +
  "팀원 4명 중 나는 데이터 전처리와 시각화를 맡았고, 다음 주 발표 자료도 내가 만들기로 했다. " +
  "처음 써 본 seaborn이 생각보다 편해서 따로 더 공부해 볼 생각이다.";

const SPINES = ["#224b46", "#2a3d52", "#38b2a6", "#0e1b2a", "#2d625b", "#1a2b3e"];

/** 책장 한 칸: 한 해. 책 12권은 달이고, 그 달에 쓴 만큼 두꺼워진다. */
function Bookshelf({
  year,
  cal,
  openMonth,
  onOpen,
  today,
}: {
  year: number;
  cal: JournalCalendar | undefined;
  openMonth: string | null;
  onOpen: (m: string) => void;
  today: string;
}) {
  const perMonth = Array.from({ length: 12 }, (_, i) => {
    const key = `${year}-${String(i + 1).padStart(2, "0")}`;
    const days = Object.entries(cal?.days ?? {}).filter(([d]) => d.startsWith(key));
    return {
      key,
      month: i + 1,
      days: days.length,
      entries: days.reduce((n, [, v]) => n + v.entries, 0),
      items: days.reduce((n, [, v]) => n + v.items, 0),
      future: key > today.slice(0, 7),
    };
  });
  return (
    <div className="relative px-2 pt-6 sm:px-6">
      <div className="flex items-end gap-1.5 overflow-x-auto px-3 pb-0 [scrollbar-width:thin] sm:justify-center sm:gap-2">
        {perMonth.map((b, i) => {
          const width = b.future ? 26 : 30 + Math.min(42, b.days * 3);
          const height = 150 + ((i * 37) % 4) * 8;
          const isOpen = openMonth === b.key;
          const color = SPINES[i % SPINES.length];
          return (
            <button
              key={b.key}
              disabled={b.future}
              onClick={() => onOpen(b.key)}
              aria-label={`${b.month}월 일기책, ${b.days}일 기록`}
              aria-pressed={isOpen}
              className={`group relative shrink-0 transition-transform duration-300 ${
                isOpen ? "-translate-y-4" : "hover:-translate-y-2"
              } disabled:cursor-default`}
              style={{ width, height }}
            >
              {/* 책 윗면(2.5D) */}
              <span
                className="absolute -top-2 left-1 h-2 origin-bottom-left"
                style={{
                  width: width - 2,
                  background: b.future ? "transparent" : "#fff7e6",
                  transform: "skewX(-40deg)",
                  boxShadow: b.future ? "none" : "inset 0 -1px 0 rgba(14,27,42,.15)",
                }}
              />
              <span
                className={`absolute inset-0 flex flex-col items-center justify-between rounded-[3px] py-3 text-white ${
                  b.future
                    ? "border-2 border-dashed border-line bg-transparent text-muted"
                    : "shadow-[inset_-6px_0_8px_rgba(0,0,0,.25),inset_3px_0_0_rgba(255,255,255,.12)]"
                }`}
                style={b.future ? undefined : { background: b.days ? color : "#c9c2b4" }}
              >
                <span className="text-[11px] font-bold tracking-wider [writing-mode:vertical-rl]">{b.month}월</span>
                {!b.future && b.days > 0 && (
                  <span className="flex flex-col items-center gap-1 text-[10px] text-white/70">
                    <span className="h-px w-4 bg-[#c9a227]" />
                    {b.days}
                    {b.items > 0 && <Leaf size={10} className="text-accent" />}
                  </span>
                )}
              </span>
              {isOpen && (
                <span className="absolute -bottom-3 left-1/2 h-1.5 w-1.5 -translate-x-1/2 rounded-full bg-accent" />
              )}
              {b.key === today.slice(0, 7) && (
                <span className="absolute top-0 right-1.5 h-6 w-2 bg-accent [clip-path:polygon(0_0,100%_0,100%_100%,50%_75%,0_100%)]" />
              )}
            </button>
          );
        })}
      </div>
      {/* 선반(2.5D): 윗면과 앞면 */}
      <div className="relative -mt-px">
        <div className="h-3 bg-gradient-to-b from-[#b08a62] to-[#9b7653] [clip-path:polygon(1.5%_0,98.5%_0,100%_100%,0_100%)]" />
        <div className="h-4 rounded-b-md bg-gradient-to-b from-[#6e4f34] to-[#4a3424] shadow-[0_10px_20px_-8px_rgba(14,27,42,.45)]" />
      </div>
    </div>
  );
}

function monthDays(month: string) {
  const [y, m] = month.split("-").map(Number);
  const first = new Date(Date.UTC(y, m - 1, 1));
  const days = new Date(Date.UTC(y, m, 0)).getUTCDate();
  const lead = first.getUTCDay();
  return { lead, days: Array.from({ length: days }, (_, i) => `${month}-${String(i + 1).padStart(2, "0")}`) };
}

function shiftDay(day: string, delta: number) {
  const d = new Date(`${day}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + delta);
  return d.toISOString().slice(0, 10);
}

const WEEK = ["일", "월", "화", "수", "목", "금", "토"];

/** 왼쪽 쪽: 그 달의 날짜. 기록한 날은 잉크가 묻고, 항목이 나온 날에는 잎이 달린다. */
function MonthPage({
  month,
  cal,
  selected,
  onSelect,
  today,
}: {
  month: string;
  cal: JournalCalendar | undefined;
  selected: string;
  onSelect: (d: string) => void;
  today: string;
}) {
  const { lead, days } = monthDays(month);
  const info = (d: string) => cal?.days[d];
  const written = days.filter((d) => info(d)).length;
  const items = days.reduce((n, d) => n + (info(d)?.items ?? 0), 0);
  return (
    <div className="flex h-full flex-col">
      <p className="section-title">Volume {Number(month.slice(5))}</p>
      <h2 className="mt-1 text-2xl font-bold">
        {month.slice(0, 4)}년 {Number(month.slice(5))}월
      </h2>
      <p className="mt-1 text-sm text-muted">
        {written}일 기록했고, 모은 항목은 {items}개다.
      </p>
      <div className="mt-5 grid grid-cols-7 gap-1 text-center text-xs">
        {WEEK.map((w) => (
          <span key={w} className="pb-1 font-medium text-muted">
            {w}
          </span>
        ))}
        {Array.from({ length: lead }, (_, i) => (
          <span key={`l${i}`} />
        ))}
        {days.map((d) => {
          const v = info(d);
          const sel = d === selected;
          const future = d > today;
          return (
            <button
              key={d}
              disabled={future}
              onClick={() => onSelect(d)}
              className={`relative aspect-square rounded-lg text-sm transition disabled:opacity-30 ${
                sel
                  ? "bg-ink font-semibold text-white"
                  : v
                    ? "bg-mint font-medium text-deep hover:bg-accent/30"
                    : "hover:bg-white"
              } ${d === today && !sel ? "ring-2 ring-accent" : ""}`}
            >
              {Number(d.slice(8))}
              {v && v.items > 0 && (
                <Leaf size={9} className={`absolute top-0.5 right-0.5 ${sel ? "text-accent" : "text-deep"}`} />
              )}
              {v && v.entries > 1 && (
                <span
                  className={`absolute bottom-0.5 left-1/2 -translate-x-1/2 text-[8px] ${sel ? "text-white/70" : "text-deep/60"}`}
                >
                  {v.entries}편
                </span>
              )}
            </button>
          );
        })}
      </div>
      <div className="mt-auto pt-5 text-xs text-muted">
        <p className="flex items-center gap-3">
          <span className="inline-flex items-center gap-1">
            <span className="h-3 w-3 rounded bg-mint" /> 기록한 날
          </span>
          <span className="inline-flex items-center gap-1">
            <Leaf size={11} className="text-deep" /> 항목이 나온 날
          </span>
        </p>
        <ul className="mt-3 space-y-0.5">
          {PROMPTS.map((p) => (
            <li key={p}>· {p}</li>
          ))}
        </ul>
      </div>
    </div>
  );
}

export default function JournalPage() {
  const qc = useQueryClient();
  const today = todayKST();
  const [year, setYear] = useState(Number(today.slice(0, 4)));
  const [month, setMonth] = useState(today.slice(0, 7));
  const [selected, setSelected] = useState(today);
  const [turn, setTurn] = useState<{ key: number; dir: "next" | "prev" }>({ key: 0, dir: "next" });
  const [body, setBody] = useState("");

  const me = useQuery({ queryKey: ["me"], queryFn: () => api<{ profile: Profile }>("/me") });
  const cal = useQuery({
    queryKey: ["calendar", year],
    queryFn: () => api<JournalCalendar>(`/journal/calendar?year=${year}`),
  });
  const entries = useQuery({
    queryKey: ["entries", month],
    queryFn: () => api<{ entries: Entry[] }>(`/entries?from=${month}-01&to=${monthDays(month).days.at(-1)}`),
  });
  const dayEntries = entries.data?.entries.filter((e) => e.entry_date === selected) ?? [];
  const writtenDays = useMemo(() => Object.keys(cal.data?.days ?? {}).sort(), [cal.data]);

  const consent = useMutation({
    mutationFn: () => post("/me/consent"),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["me"] }),
  });
  const create = useMutation({
    mutationFn: () => post("/entries", { entry_date: selected, body }),
    onSuccess: () => {
      setBody("");
      ["entries", "calendar", "stats", "growth"].forEach((k) => qc.invalidateQueries({ queryKey: [k] }));
    },
  });

  useEffect(() => {
    const fill = () => {
      setBody((b) => b || SAMPLE_ENTRY);
      setTimeout(() => document.querySelector<HTMLElement>('[data-tour="editor"] textarea')?.focus(), 50);
    };
    window.addEventListener("rp:sample-entry", fill);
    return () => window.removeEventListener("rp:sample-entry", fill);
  }, []);

  function go(day: string, dir?: "next" | "prev") {
    if (day > today) return;
    setTurn((t) => ({ key: t.key + 1, dir: dir ?? (day >= selected ? "next" : "prev") }));
    setSelected(day);
    setMonth(day.slice(0, 7));
    if (Number(day.slice(0, 4)) !== year) setYear(Number(day.slice(0, 4)));
  }
  // 도감처럼 넘긴다: 기록이 있는 앞뒤 날로 간다. 없으면 하루씩.
  const prevDay = [...writtenDays].reverse().find((d) => d < selected) ?? shiftDay(selected, -1);
  const nextWritten = writtenDays.find((d) => d > selected);
  const nextDay = nextWritten ?? (selected < today ? shiftDay(selected, 1) : null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement | null)?.tagName;
      if (tag === "TEXTAREA" || tag === "INPUT" || tag === "SELECT") return;
      if (e.key === "ArrowLeft") go(prevDay, "prev");
      if (e.key === "ArrowRight" && nextDay) go(nextDay, "next");
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  const consented = !!me.data?.profile.llm_consent_at;
  const [y, m, d] = selected.split("-").map(Number);
  const weekday = WEEK[new Date(y, m - 1, d).getDay()];
  const years = cal.data?.years ?? [year];

  return (
    <div>
      <PageHeader
        eyebrow="Journal"
        title="일기 책장"
        description="한 칸이 한 해, 책 한 권이 한 달이다. 쓸수록 책이 두꺼워진다. 책을 펼쳐 쓰고, 지난 쪽을 넘겨 본다."
        actions={
          <div className="flex gap-1">
            {years.map((yy) => (
              <button
                key={yy}
                onClick={() => {
                  setYear(yy);
                  const m0 = yy === Number(today.slice(0, 4)) ? today.slice(0, 7) : `${yy}-12`;
                  setMonth(m0);
                }}
                className={`rounded-full px-3 py-1 text-sm ${yy === year ? "bg-ink text-white" : "bg-white text-muted ring-1 ring-line hover:text-ink"}`}
              >
                {yy}
              </button>
            ))}
          </div>
        }
      />

      <section className="mb-8 rounded-3xl bg-gradient-to-b from-cream to-paper pb-4" data-tour="bookshelf">
        <Bookshelf
          year={year}
          cal={cal.data}
          openMonth={month.startsWith(String(year)) ? month : null}
          today={today}
          onOpen={(mm) => {
            const days = writtenDays.filter((dd) => dd.startsWith(mm));
            const target = mm === today.slice(0, 7) ? today : (days.at(-1) ?? `${mm}-01`);
            go(target);
          }}
        />
      </section>

      {me.data && !consented && (
        <div className="mb-4 flex flex-wrap items-center gap-3 rounded-2xl border border-accent/40 bg-mint/60 p-4 text-sm">
          <ShieldCheck className="shrink-0 text-deep" size={20} />
          <p className="min-w-0 flex-1">
            일기를 분석하려면 내용이 외부 LLM API로 전송된다는 데 동의해야 한다. 동의하기 전에도 일기는 쓸 수 있다.
          </p>
          <button className="btn btn-primary btn-sm" onClick={() => consent.mutate()} disabled={consent.isPending}>
            동의하고 분석 켜기
          </button>
        </div>
      )}

      {/* 펼친 책 */}
      <div key={month} className="book-open relative rounded-[22px] bg-[#6e4f34] p-2 shadow-lift sm:p-3">
        <div className="grid overflow-hidden rounded-2xl bg-[#fffcf5] lg:grid-cols-[minmax(280px,0.8fr)_1.2fr]">
          <div className="relative border-b border-line/70 bg-gradient-to-r from-[#fff7e6] to-[#fffcf5] p-6 lg:border-r lg:border-b-0">
            <MonthPage month={month} cal={cal.data} selected={selected} onSelect={(dd) => go(dd)} today={today} />
            <span className="pointer-events-none absolute inset-y-0 right-0 hidden w-6 bg-gradient-to-l from-ink/10 to-transparent lg:block" />
          </div>
          <div
            key={turn.key}
            className={`relative min-h-[520px] p-6 ${turn.dir === "next" ? "page-next" : "page-prev"}`}
          >
            <span className="pointer-events-none absolute inset-y-0 left-0 hidden w-6 bg-gradient-to-r from-ink/10 to-transparent lg:block" />
            <div className="mb-4 flex items-center gap-2">
              <button className="btn-ghost rounded-lg p-1.5" onClick={() => go(prevDay, "prev")} aria-label="앞 쪽">
                <ChevronLeft size={18} />
              </button>
              <div className="mr-auto">
                <p className="text-xs text-muted">{selected === today ? "오늘" : selected}</p>
                <h3 className="text-xl font-bold">
                  {m}월 {d}일 {weekday}요일
                </h3>
              </div>
              <span className="hidden text-xs text-muted sm:inline">← → 로 넘긴다</span>
              <button
                className="btn-ghost rounded-lg p-1.5 disabled:opacity-30"
                onClick={() => nextDay && go(nextDay, "next")}
                disabled={!nextDay}
                aria-label="다음 쪽"
              >
                <ChevronRight size={18} />
              </button>
            </div>

            <div className="rounded-xl border border-line/80 bg-white" data-tour="editor">
              <textarea
                className="block min-h-36 w-full resize-y rounded-t-xl border-0 bg-[repeating-linear-gradient(transparent,transparent_31px,#ebe4d6_31px,#ebe4d6_32px)] bg-local px-5 pt-[6px] pb-4 text-[15px] leading-8 outline-none placeholder:text-muted/60"
                placeholder={
                  dayEntries.length
                    ? "이 날에 더 적을 것이 있으면 이어서 쓴다."
                    : "이 쪽은 아직 비어 있다. 무엇을 했는지 편하게 적어 보세요."
                }
                value={body}
                onChange={(e) => setBody(e.target.value)}
                maxLength={20000}
              />
              <div className="flex items-center gap-3 border-t border-line/70 px-4 py-2.5">
                <span className="text-xs text-muted">{body.length.toLocaleString()} / 20,000</span>
                <button
                  className="btn btn-primary btn-sm ml-auto"
                  onClick={() => create.mutate()}
                  disabled={!body.trim() || create.isPending}
                >
                  <NotebookPen size={14} /> 이 쪽에 쓰기
                </button>
              </div>
            </div>
            <ErrorText error={create.error} />

            <div className="mt-5 space-y-4">
              {dayEntries.length === 0 && entries.isSuccess && (
                <p className="flex items-center gap-2 py-6 text-sm text-muted">
                  <BookOpen size={16} /> 이 날에 쓴 일기가 없다. 한두 문장이면 충분하다.
                </p>
              )}
              {dayEntries.map((e) => (
                <EntryCard key={e.id} entry={e} />
              ))}
            </div>
            <ErrorText error={entries.error ?? me.error ?? cal.error} />
          </div>
        </div>
      </div>
    </div>
  );
}
