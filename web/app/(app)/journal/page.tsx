"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { ErrorText } from "@/components/ErrorText";
import { api, patch, post } from "@/lib/api";
import { todayKST } from "@/lib/text";
import { PROPOSAL_KIND_LABELS, type Entry, type Job, type Profile, type ProposalKind } from "@/lib/types";

type EntryDetail = Entry & {
  proposals: { id: string; kind: ProposalKind; status: string; quote: string | null }[];
  sources: { id: string; item_id: string; item_title: string; item_status: string; quote: string }[];
  job: { id: string; status: Job["status"] } | null;
};

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
}: {
  month: string;
  setMonth: (m: string) => void;
  selected: string;
  onSelect: (d: string) => void;
  marked: Set<string>;
}) {
  const { lead, days } = monthDays(month);
  return (
    <div className="card">
      <div className="mb-2 flex items-center justify-between text-sm">
        <button className="px-2 text-zinc-500" onClick={() => setMonth(shiftMonth(month, -1))} aria-label="이전 달">
          ‹
        </button>
        <span className="font-medium">{month.replace("-", ".")}</span>
        <button className="px-2 text-zinc-500" onClick={() => setMonth(shiftMonth(month, 1))} aria-label="다음 달">
          ›
        </button>
      </div>
      <div className="grid grid-cols-7 gap-1 text-center text-xs">
        {["일", "월", "화", "수", "목", "금", "토"].map((d) => (
          <span key={d} className="text-zinc-400">
            {d}
          </span>
        ))}
        {Array.from({ length: lead }, (_, i) => (
          <span key={`lead-${i}`} />
        ))}
        {days.map((d) => (
          <button
            key={d}
            onClick={() => onSelect(d)}
            className={`relative rounded py-1.5 ${
              d === selected ? "bg-brand text-white" : "hover:bg-zinc-100"
            }`}
          >
            {Number(d.slice(8))}
            {marked.has(d) && (
              <span
                className={`absolute bottom-0.5 left-1/2 h-1 w-1 -translate-x-1/2 rounded-full ${
                  d === selected ? "bg-white" : "bg-brand"
                }`}
              />
            )}
          </button>
        ))}
      </div>
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
    // 분석이 끝나면 상단 검토 배지와 검토 큐를 바로 갱신한다.
    if (status === "succeeded") {
      qc.invalidateQueries({ queryKey: ["pending-count"] });
      qc.invalidateQueries({ queryKey: ["proposals"] });
    }
  }, [status, qc]);
  const d = detail.data;
  if (!d) return null;
  const pending = d.proposals.filter((p) => p.status === "pending");

  return (
    <div className="mt-3 space-y-2 text-sm">
      {(d.extraction_status === "queued" || d.extraction_status === "running") && (
        <p className="text-zinc-500">기록을 분석하고 있다.</p>
      )}
      {d.extraction_status === "failed" && (
        <p className="text-red-700">분석에 실패했다. 다시 분석을 눌러 보세요.</p>
      )}
      {d.extraction_status === null && (
        <p className="text-zinc-500">외부 LLM 처리에 동의하면 이 일기를 분석할 수 있다.</p>
      )}
      {d.extraction_status === "succeeded" && job.data?.result && (
        <p>
          제안 {String(job.data.result.proposals ?? 0)}건, 질문 {String(job.data.result.followups ?? 0)}건을
          찾았다.{" "}
          {pending.length > 0 && (
            <Link href="/review" className="text-brand underline">
              검토 큐로 가기
            </Link>
          )}
        </p>
      )}
      {pending.length > 0 && (
        <ul className="space-y-1">
          {pending.map((p) => (
            <li key={p.id} className="text-zinc-600">
              <span className="chip mr-2">{PROPOSAL_KIND_LABELS[p.kind]}</span>
              {p.quote}
            </li>
          ))}
        </ul>
      )}
      {d.sources.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {d.sources
            .filter((s) => s.item_status === "approved")
            .map((s) => (
              <Link key={s.id} href={`/portfolio/${s.item_id}`} className="chip hover:bg-brand-soft">
                {s.item_title}
              </Link>
            ))}
        </div>
      )}
      {d.extraction_status !== "queued" && d.extraction_status !== "running" && (
        <button className="btn" onClick={() => reextract.mutate()} disabled={reextract.isPending}>
          다시 분석
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

  return (
    <article className="card">
      {editing ? (
        <>
          <textarea className="input min-h-32" value={body} onChange={(e) => setBody(e.target.value)} />
          <p className="mt-1 text-xs text-zinc-500">수정만으로는 다시 분석하지 않는다. 필요하면 저장 뒤 다시 분석을 누른다.</p>
          <div className="mt-2 flex gap-2">
            <button className="btn btn-primary" onClick={() => save.mutate()} disabled={save.isPending}>
              저장
            </button>
            <button className="btn" onClick={() => setEditing(false)}>
              취소
            </button>
          </div>
        </>
      ) : (
        <p className="whitespace-pre-wrap text-sm leading-relaxed">{entry.body}</p>
      )}
      <ExtractionStatus entry={entry} />
      {!editing && (
        <div className="mt-3 flex gap-3 text-xs text-zinc-500">
          <button onClick={() => setEditing(true)}>수정</button>
          <button
            onClick={() => {
              if (confirm("이 일기를 지운다. 승인한 항목은 남고 근거 연결만 사라진다. 계속할까요?")) remove.mutate();
            }}
          >
            삭제
          </button>
        </div>
      )}
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
    queryFn: () =>
      api<{ entries: Entry[] }>(`/entries?from=${month}-01&to=${shiftMonth(month, 1)}-01`),
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
    },
  });
  const consented = !!me.data?.profile.llm_consent_at;

  return (
    <div className="grid gap-6 md:grid-cols-[280px_1fr]">
      <aside className="space-y-3">
        <Calendar
          month={month}
          setMonth={setMonth}
          selected={selected}
          onSelect={(d) => {
            setSelected(d);
            setMonth(d.slice(0, 7));
          }}
          marked={marked}
        />
      </aside>
      <section className="space-y-4">
        <h1 className="text-lg font-semibold">{selected.replaceAll("-", ".")} 일기</h1>
        {me.data && !consented && (
          <div className="card space-y-2 border-amber-300 bg-amber-50 text-sm">
            <p>
              일기를 분석하려면 일기 내용이 외부 LLM API로 전송된다는 데 동의해야 한다. 동의하기 전에도 일기는 쓸 수 있다.
            </p>
            <button className="btn" onClick={() => consent.mutate()} disabled={consent.isPending}>
              동의하고 분석 켜기
            </button>
          </div>
        )}
        <div className="card space-y-2">
          <textarea
            className="input min-h-40"
            placeholder="오늘 무엇을 했는지 편하게 적어 보세요. 프로젝트, 대회, 공부, 활동 무엇이든 좋다."
            value={body}
            onChange={(e) => setBody(e.target.value)}
            maxLength={20000}
          />
          <div className="flex items-center justify-between">
            <span className="text-xs text-zinc-400">{body.length.toLocaleString()} / 20,000</span>
            <button
              className="btn btn-primary"
              onClick={() => create.mutate()}
              disabled={!body.trim() || create.isPending}
            >
              저장
            </button>
          </div>
          <ErrorText error={create.error} />
        </div>
        {dayEntries.length === 0 && entries.isSuccess && (
          <p className="text-sm text-zinc-500">이 날짜에 쓴 일기가 없다. 첫 일기를 써 보세요.</p>
        )}
        {dayEntries.map((e) => (
          <EntryCard key={e.id} entry={e} />
        ))}
        <ErrorText error={entries.error ?? me.error} />
      </section>
    </div>
  );
}
