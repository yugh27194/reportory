"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, ChevronLeft, ChevronRight, NotebookPen, Pencil, RefreshCw, ShieldCheck, Trash2 } from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { ErrorText } from "@/components/ErrorText";
import { EmptyState, PageHeader, Spinner } from "@/components/ui";
import { api, patch, post } from "@/lib/api";
import { todayKST } from "@/lib/text";
import { PROPOSAL_KIND_LABELS, type Entry, type Job, type Profile, type ProposalKind } from "@/lib/types";

type EntryDetail = Entry & {
  proposals: { id: string; kind: ProposalKind; status: string; quote: string | null }[];
  sources: { id: string; item_id: string; item_title: string; item_status: string; quote: string }[];
  job: { id: string; status: Job["status"] } | null;
};

const PROMPTS = [
  "오늘 무엇을 만들었나요?",
  "새로 배운 기술이 있나요?",
  "팀에서 맡은 역할은?",
  "결과나 수치가 나왔나요?",
];

function monthDays(month: string) {
  const [y, m] = month.split("-").map(Number);
  const first = new Date(Date.UTC(y, m - 1, 1));
  const days = new Date(Date.UTC(y, m, 0)).getUTCDate();
  const lead = first.getUTCDay();
  return { lead, days: Array.from({ length: days }, (_, i) => `${month}-${String(i + 1).padStart(2, "0")}`) };
}

function shiftMonth(month: string, delta: number) {
  const [y, m] = month.split("-").map(Number);
  const d = new Date(Date.UTC(y, m - 1 + delta, 1));
  return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, "0")}`;
}

function Calendar({
  month,
  setMonth,
  selected,
  onSelect,
  marked,
  today,
}: {
  month: string;
  setMonth: (m: string) => void;
  selected: string;
  onSelect: (d: string) => void;
  marked: Set<string>;
  today: string;
}) {
  const { lead, days } = monthDays(month);
  return (
    <div className="card">
      <div className="mb-3 flex items-center justify-between">
        <button className="btn-ghost rounded-lg p-1.5" onClick={() => setMonth(shiftMonth(month, -1))} aria-label="이전 달">
          <ChevronLeft size={18} />
        </button>
        <span className="font-semibold">
          {month.slice(0, 4)}년 {Number(month.slice(5))}월
        </span>
        <button className="btn-ghost rounded-lg p-1.5" onClick={() => setMonth(shiftMonth(month, 1))} aria-label="다음 달">
          <ChevronRight size={18} />
        </button>
      </div>
      <div className="grid grid-cols-7 gap-1 text-center text-xs">
        {["일", "월", "화", "수", "목", "금", "토"].map((d) => (
          <span key={d} className="pb-1 font-medium text-muted">
            {d}
          </span>
        ))}
        {Array.from({ length: lead }, (_, i) => (
          <span key={`lead-${i}`} />
        ))}
        {days.map((d) => {
          const isSel = d === selected;
          const has = marked.has(d);
          return (
            <button
              key={d}
              onClick={() => onSelect(d)}
              className={`relative aspect-square rounded-lg text-sm transition ${
                isSel
                  ? "bg-deep font-semibold text-white"
                  : has
                    ? "bg-mint font-medium text-deep hover:bg-accent/30"
                    : "hover:bg-cream"
              } ${d === today && !isSel ? "ring-2 ring-accent" : ""}`}
            >
              {Number(d.slice(8))}
            </button>
          );
        })}
      </div>
      <p className="mt-3 flex items-center gap-2 text-xs text-muted">
        <span className="h-3 w-3 rounded bg-mint" /> 일기를 쓴 날
      </p>
    </div>
  );
}

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
  const pending = d.proposals.filter((p) => p.status === "pending");
  const linked = d.sources.filter((s) => s.item_status === "approved");

  return (
    <div className="mt-4 space-y-3 border-t border-line/70 pt-4 text-sm">
      {(status === "queued" || status === "running") && <Spinner label="기록을 분석하고 있다." />}
      {status === "failed" && <p className="text-red-700">분석에 실패했다. 다시 분석을 눌러 보세요.</p>}
      {status === null && <p className="text-muted">외부 LLM 처리에 동의하면 이 일기를 분석할 수 있다.</p>}
      {status === "succeeded" && job.data?.result && (
        <p className="flex flex-wrap items-center gap-2">
          <CheckCircle2 size={16} className="text-accent-2" />
          제안 {String(job.data.result.proposals ?? 0)}건, 질문 {String(job.data.result.followups ?? 0)}건을 찾았다.
          {pending.length > 0 && (
            <Link href="/review" className="font-medium text-deep underline underline-offset-2">
              검토 큐로 가기
            </Link>
          )}
        </p>
      )}
      {pending.length > 0 && (
        <ul className="space-y-1.5">
          {pending.map((p) => (
            <li key={p.id} className="flex gap-2 text-muted">
              <span className="chip shrink-0">{PROPOSAL_KIND_LABELS[p.kind]}</span>
              <span className="line-clamp-1">“{p.quote}”</span>
            </li>
          ))}
        </ul>
      )}
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
      qc.invalidateQueries({ queryKey: ["pending-count"] });
    },
  });
  const time = new Date(entry.created_at).toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit" });

  return (
    <article className="card">
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
          <p className="mt-1 text-xs text-muted">수정만으로는 다시 분석하지 않는다. 필요하면 저장한 뒤 다시 분석을 누른다.</p>
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

export default function JournalPage() {
  const qc = useQueryClient();
  const today = todayKST();
  const [selected, setSelected] = useState(today);
  const [month, setMonth] = useState(today.slice(0, 7));
  const [body, setBody] = useState("");

  const me = useQuery({ queryKey: ["me"], queryFn: () => api<{ profile: Profile }>("/me") });
  const entries = useQuery({
    queryKey: ["entries", month],
    queryFn: () => api<{ entries: Entry[] }>(`/entries?from=${month}-01&to=${monthDays(month).days.at(-1)}`),
  });
  const marked = useMemo(() => new Set(entries.data?.entries.map((e) => e.entry_date)), [entries.data]);
  const dayEntries = entries.data?.entries.filter((e) => e.entry_date === selected) ?? [];

  const consent = useMutation({
    mutationFn: () => post("/me/consent"),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["me"] }),
  });
  const create = useMutation({
    mutationFn: () => post("/entries", { entry_date: selected, body }),
    onSuccess: () => {
      setBody("");
      qc.invalidateQueries({ queryKey: ["entries"] });
      qc.invalidateQueries({ queryKey: ["stats"] });
    },
  });
  const consented = !!me.data?.profile.llm_consent_at;
  const [y, m, d] = selected.split("-").map(Number);
  const weekday = ["일", "월", "화", "수", "목", "금", "토"][new Date(y, m - 1, d).getDay()];

  return (
    <div>
      <PageHeader
        eyebrow="Journal"
        title={`${m}월 ${d}일 ${weekday}요일`}
        description={selected === today ? "오늘의 기록을 남겨 보세요." : "지난 날의 기록도 언제든 더할 수 있다."}
      />
      <div className="grid gap-6 lg:grid-cols-[300px_1fr]">
        <aside className="space-y-4">
          <Calendar
            month={month}
            setMonth={setMonth}
            selected={selected}
            onSelect={(v) => {
              setSelected(v);
              setMonth(v.slice(0, 7));
            }}
            marked={marked}
            today={today}
          />
          <div className="rounded-2xl bg-cream p-4 text-sm">
            <p className="mb-2 font-semibold text-deep">이런 걸 적어 보세요</p>
            <ul className="space-y-1 text-muted">
              {PROMPTS.map((p) => (
                <li key={p}>· {p}</li>
              ))}
            </ul>
          </div>
        </aside>
        <section className="space-y-4">
          {me.data && !consented && (
            <div className="flex flex-wrap items-center gap-3 rounded-2xl border border-accent/40 bg-mint/60 p-4 text-sm">
              <ShieldCheck className="shrink-0 text-deep" size={20} />
              <p className="min-w-0 flex-1">
                일기를 분석하려면 내용이 외부 LLM API로 전송된다는 데 동의해야 한다. 동의하기 전에도 일기는 쓸 수 있다.
              </p>
              <button className="btn btn-primary btn-sm" onClick={() => consent.mutate()} disabled={consent.isPending}>
                동의하고 분석 켜기
              </button>
            </div>
          )}
          <div className="card p-0">
            <textarea
              className="block min-h-44 w-full resize-y rounded-t-2xl border-0 bg-transparent p-5 text-[15px] leading-relaxed outline-none placeholder:text-muted/60"
              placeholder="오늘 무엇을 했는지 편하게 적어 보세요. 프로젝트, 대회, 공부, 활동 무엇이든 좋다."
              value={body}
              onChange={(e) => setBody(e.target.value)}
              maxLength={20000}
            />
            <div className="flex items-center gap-3 border-t border-line/70 px-5 py-3">
              <span className="text-xs text-muted">{body.length.toLocaleString()} / 20,000</span>
              <button
                className="btn btn-primary ml-auto"
                onClick={() => create.mutate()}
                disabled={!body.trim() || create.isPending}
              >
                <NotebookPen size={16} /> 저장
              </button>
            </div>
          </div>
          <ErrorText error={create.error} />
          {dayEntries.length === 0 && entries.isSuccess && (
            <EmptyState icon={NotebookPen} title="이 날짜에 쓴 일기가 없다" description="첫 일기를 써 보세요. 한두 문장이면 충분하다." />
          )}
          {dayEntries.map((e) => (
            <EntryCard key={e.id} entry={e} />
          ))}
          <ErrorText error={entries.error ?? me.error} />
        </section>
      </div>
    </div>
  );
}
