"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronDown, ClipboardList, Plus, SquareArrowOutUpRight, X } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { ErrorText } from "@/components/ErrorText";
import { EmptyState, PageHeader } from "@/components/ui";
import { api, post } from "@/lib/api";
import { ddayLabel } from "@/lib/dday";
import {
  APPLICATION_STATUS_LABELS,
  CATEGORY_LABELS,
  NEXT_STATUSES,
  type Application,
  type ApplicationDetail,
  type ApplicationStatus,
  type OpportunityCategory,
} from "@/lib/types";

const COLUMNS: { key: string; label: string; statuses: ApplicationStatus[]; hint: string }[] = [
  { key: "interested", label: "관심", statuses: ["interested"], hint: "지원을 고민 중이다" },
  {
    key: "applied",
    label: "지원·결과 대기",
    statuses: ["applied", "awaiting_result"],
    hint: "마감이 지나면 결과 대기로 옮겨진다",
  },
  { key: "active", label: "합격·활동 중", statuses: ["accepted", "active"], hint: "합격하면 모아보기에 항목이 생긴다" },
  { key: "done", label: "끝남", statuses: ["completed", "rejected", "withdrawn"], hint: "완료·불합격·취소" },
];

const ACTION_LABELS: Partial<Record<ApplicationStatus, string>> = {
  applied: "지원했다",
  accepted: "합격했다",
  rejected: "불합격",
  active: "활동 시작",
  completed: "활동을 마쳤다",
  withdrawn: "지원 취소",
};

const SOURCE_LABELS: Record<string, string> = {
  manual: "직접",
  diary: "일기",
  reminder: "알림",
  evidence: "증빙",
  system: "자동",
  email: "메일",
};

function useRefresh() {
  const qc = useQueryClient();
  return () =>
    ["applications", "application", "recommendations", "items", "stats", "growth"].forEach((k) =>
      qc.invalidateQueries({ queryKey: [k] }),
    );
}

function Card({ a, open, onToggle }: { a: Application; open: boolean; onToggle: () => void }) {
  const refresh = useRefresh();
  const [reflection, setReflection] = useState(a.reflection ?? "");
  const detail = useQuery({
    queryKey: ["application", a.id],
    queryFn: () => api<ApplicationDetail>(`/applications/${a.id}`),
    enabled: open,
  });
  const move = useMutation({
    mutationFn: (to: ApplicationStatus) => post(`/applications/${a.id}/transition`, { to_status: to }),
    onSuccess: refresh,
  });
  const saveReflection = useMutation({
    mutationFn: () => post(`/applications/${a.id}/reflection`, { reflection }),
    onSuccess: refresh,
  });
  const next = NEXT_STATUSES[a.status];
  const needsReflection = (a.status === "rejected" || a.status === "completed") && !a.reflection;

  return (
    <li className={`rounded-xl border bg-white p-3 shadow-card ${open ? "border-accent" : "border-line/80"}`}>
      <button className="flex w-full items-start gap-2 text-left" onClick={onToggle}>
        <span className="min-w-0 flex-1">
          <span className="block leading-snug font-semibold">{a.title}</span>
          <span className="mt-0.5 block text-xs text-muted">
            {[CATEGORY_LABELS[a.category], a.organizer].filter(Boolean).join(" · ")}
          </span>
        </span>
        <ChevronDown size={16} className={`mt-1 shrink-0 text-muted transition ${open ? "rotate-180" : ""}`} />
      </button>
      <div className="mt-2 flex flex-wrap items-center gap-1.5 text-xs">
        <span className="chip chip-cream">{APPLICATION_STATUS_LABELS[a.status]}</span>
        {a.status === "interested" && a.apply_deadline && (
          <span className="chip chip-ink">{ddayLabel(a.apply_deadline)}</span>
        )}
        {a.item_id && (
          <Link href={`/portfolio/${a.item_id}`} className="chip hover:bg-accent/40">
            모아보기 항목
          </Link>
        )}
      </div>
      {next.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {next.map((s) => (
            <button
              key={s}
              className={`btn btn-sm ${s === "accepted" || s === "applied" || s === "completed" ? "btn-primary" : ""}`}
              disabled={move.isPending}
              onClick={() => move.mutate(s)}
            >
              {ACTION_LABELS[s] ?? APPLICATION_STATUS_LABELS[s]}
            </button>
          ))}
        </div>
      )}
      <ErrorText error={move.error} />
      {needsReflection && (
        <div className="mt-3 rounded-lg bg-cream/70 p-2.5">
          <p className="mb-1.5 text-xs font-semibold text-deep">한 줄 회고를 남긴다</p>
          <textarea
            className="input min-h-16 text-sm"
            placeholder={a.status === "rejected" ? "무엇이 아쉬웠고 다음엔 무엇을 바꿀까요?" : "무엇을 얻었나요?"}
            value={reflection}
            onChange={(e) => setReflection(e.target.value)}
            maxLength={1000}
          />
          <button
            className="btn btn-sm mt-1.5"
            disabled={!reflection.trim() || saveReflection.isPending}
            onClick={() => saveReflection.mutate()}
          >
            저장
          </button>
        </div>
      )}
      {open && detail.data && (
        <div className="mt-3 space-y-2 border-t border-line/70 pt-3 text-xs text-muted">
          <p>
            {[
              detail.data.apply_deadline && `마감 ${detail.data.apply_deadline}`,
              detail.data.result_announce_on && `발표 ${detail.data.result_announce_on}`,
              detail.data.activity_start && `활동 ${detail.data.activity_start}~${detail.data.activity_end ?? ""}`,
            ]
              .filter(Boolean)
              .join(" · ") || "날짜 정보가 없다."}
          </p>
          {detail.data.reflection && <p className="text-ink/80">회고: {detail.data.reflection}</p>}
          <ol className="space-y-0.5">
            {detail.data.events.map((e, i) => (
              <li key={i}>
                {new Date(e.created_at).toLocaleDateString("ko-KR")} · {APPLICATION_STATUS_LABELS[e.to_status]} (
                {SOURCE_LABELS[e.source] ?? e.source})
              </li>
            ))}
          </ol>
          {detail.data.opportunity && (
            <a
              href={detail.data.opportunity.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-deep hover:underline"
            >
              공고 원문 <SquareArrowOutUpRight size={12} />
            </a>
          )}
        </div>
      )}
    </li>
  );
}

function AddForm({ onDone }: { onDone: () => void }) {
  const refresh = useRefresh();
  const [title, setTitle] = useState("");
  const [organizer, setOrganizer] = useState("");
  const [category, setCategory] = useState<OpportunityCategory>("contest");
  const [deadline, setDeadline] = useState("");
  const add = useMutation({
    mutationFn: () =>
      post("/applications", {
        title: title.trim(),
        organizer: organizer.trim() || null,
        category,
        apply_deadline: deadline || null,
      }),
    onSuccess: () => {
      refresh();
      onDone();
    },
  });
  return (
    <form
      className="card mb-6 grid gap-3 sm:grid-cols-[2fr_1.2fr_1fr_1fr_auto] sm:items-end"
      onSubmit={(e) => {
        e.preventDefault();
        add.mutate();
      }}
    >
      <label>
        <span className="label">이름</span>
        <input
          className="input"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="예: OO 데이터 해커톤"
          required
          maxLength={200}
        />
      </label>
      <label>
        <span className="label">주최</span>
        <input className="input" value={organizer} onChange={(e) => setOrganizer(e.target.value)} maxLength={200} />
      </label>
      <label>
        <span className="label">분류</span>
        <select className="input" value={category} onChange={(e) => setCategory(e.target.value as OpportunityCategory)}>
          {Object.entries(CATEGORY_LABELS).map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
        </select>
      </label>
      <label>
        <span className="label">마감일</span>
        <input type="date" className="input" value={deadline} onChange={(e) => setDeadline(e.target.value)} />
      </label>
      <button className="btn btn-primary" disabled={!title.trim() || add.isPending}>
        추가
      </button>
      <ErrorText error={add.error} />
    </form>
  );
}

function Board() {
  const params = useSearchParams();
  const [openId, setOpenId] = useState<string | null>(params.get("open"));
  const [adding, setAdding] = useState(false);
  const apps = useQuery({
    queryKey: ["applications"],
    queryFn: () => api<{ applications: Application[] }>("/applications"),
  });
  const all = apps.data?.applications ?? [];

  return (
    <div>
      <PageHeader
        eyebrow="Applications"
        title="지원 관리"
        description="관심 → 지원 → 결과 → 활동까지 한눈에 본다. 일기에 결과를 쓰면 상태를 바꾸자는 제안이 생긴다."
        actions={
          <button className="btn btn-primary" onClick={() => setAdding((v) => !v)}>
            {adding ? <X size={16} /> : <Plus size={16} />} {adding ? "닫기" : "직접 추가"}
          </button>
        }
      />
      {adding && <AddForm onDone={() => setAdding(false)} />}
      <ErrorText error={apps.error} />
      {apps.isSuccess && all.length === 0 ? (
        <EmptyState
          icon={ClipboardList}
          title="아직 지원 항목이 없다"
          description="활동 추천에서 '관심'이나 '지원함'을 누르면 여기에 쌓인다. 직접 추가해도 된다."
          action={
            <Link href="/recommendations" className="btn btn-primary">
              활동 추천 보기
            </Link>
          }
        />
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {COLUMNS.map((col) => {
            const list = all.filter((a) => col.statuses.includes(a.status));
            return (
              <section key={col.key} className="rounded-2xl bg-ink/[.03] p-3 ring-1 ring-line/70">
                <h2 className="flex items-baseline gap-2 px-1 font-semibold">
                  {col.label} <span className="text-sm text-muted">{list.length}</span>
                </h2>
                <p className="mb-3 px-1 text-xs text-muted">{col.hint}</p>
                <ul className="space-y-2.5">
                  {list.map((a) => (
                    <Card
                      key={a.id}
                      a={a}
                      open={openId === a.id}
                      onToggle={() => setOpenId(openId === a.id ? null : a.id)}
                    />
                  ))}
                </ul>
              </section>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default function ApplicationsPage() {
  return (
    <Suspense>
      <Board />
    </Suspense>
  );
}
