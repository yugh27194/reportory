"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, CheckCheck, MessageCircleQuestion, Plus, X } from "lucide-react";
import { useState } from "react";
import { ErrorText } from "@/components/ErrorText";
import { TypeIcon } from "@/components/ui";
import { api, post } from "@/lib/api";
import { formatPeriod } from "@/lib/text";
import { ITEM_TYPE_LABELS, PROPOSAL_KIND_LABELS, type Followup, type Proposal } from "@/lib/types";

type FollowupRow = Followup & { entry_id: string | null };

export function usePending() {
  const proposals = useQuery({
    queryKey: ["proposals"],
    queryFn: () => api<{ proposals: Proposal[] }>("/proposals?status=pending"),
  });
  const followups = useQuery({
    queryKey: ["followups"],
    queryFn: () => api<{ followups: FollowupRow[] }>("/followups?status=open"),
  });
  return { proposals, followups };
}

function useRefresh() {
  const qc = useQueryClient();
  return () => ["proposals", "followups", "pending-count", "items", "stats", "item"].forEach((k) => qc.invalidateQueries({ queryKey: [k] }));
}

/** 제안 하나: 제목을 바로 고치고 '추가' 또는 '빼기'만 누르면 된다. */
export function ProposalRow({ p }: { p: Proposal }) {
  const refresh = useRefresh();
  const item = p.item;
  const [title, setTitle] = useState(item?.title ?? "");
  const accept = useMutation({
    mutationFn: () =>
      post(
        `/proposals/${p.id}/accept`,
        p.kind === "create_item" && item && title.trim() && title.trim() !== item.title
          ? { edited_payload: { title: title.trim() } }
          : undefined,
      ),
    onSuccess: refresh,
  });
  const reject = useMutation({ mutationFn: () => post(`/proposals/${p.id}/reject`), onSuccess: refresh });
  const busy = accept.isPending || reject.isPending;
  const patch = (p.payload.patch ?? {}) as { summary_append?: string; summary_replace?: string; skills_add?: string[] };
  const isNew = p.kind === "create_item";

  return (
    <li className="rounded-xl border border-line/80 bg-white p-3">
      <div className="flex items-start gap-3">
        {item ? <TypeIcon type={item.type} size="sm" /> : <span className="h-7 w-7" />}
        <div className="min-w-0 flex-1 space-y-1">
          <p className="text-xs text-muted">
            {isNew ? "새 경험" : PROPOSAL_KIND_LABELS[p.kind]}
            {item && ` · ${ITEM_TYPE_LABELS[item.type]}`}
            {item && !isNew && ` · ${item.title}`}
          </p>
          {isNew && item ? (
            <input
              className="w-full rounded-md border border-transparent bg-transparent px-1 py-0.5 -ml-1 text-sm font-semibold outline-none hover:border-line focus:border-accent focus:bg-white"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              aria-label="경험 제목"
              title="눌러서 제목을 고칠 수 있다"
            />
          ) : (
            <p className="text-sm font-medium">{patch.summary_append || patch.summary_replace || (p.kind === "link_entry" ? "이 일기를 근거로 연결한다." : "")}</p>
          )}
          {isNew && item && (
            <p className="text-xs text-muted">
              {[item.organization, item.role, formatPeriod(item.start_date, item.end_date, item.is_ongoing)].filter(Boolean).join(" · ")}
            </p>
          )}
          {(p.item_skills?.length > 0 || (patch.skills_add?.length ?? 0) > 0) && (
            <div className="flex flex-wrap gap-1">
              {(isNew ? p.item_skills : patch.skills_add ?? []).map((s) => (
                <span key={s} className="chip">
                  {s}
                </span>
              ))}
            </div>
          )}
          {p.quote && <p className="line-clamp-2 border-l-2 border-accent pl-2 text-xs text-muted">“{p.quote}”</p>}
        </div>
        <div className="flex shrink-0 gap-1">
          <button className="btn btn-primary btn-sm" disabled={busy} onClick={() => accept.mutate()} title="경험에 추가">
            {isNew ? <Plus size={14} /> : <Check size={14} />} {isNew ? "추가" : "반영"}
          </button>
          <button className="btn btn-ghost btn-sm" disabled={busy} onClick={() => reject.mutate()} title="빼기" aria-label="빼기">
            <X size={14} />
          </button>
        </div>
      </div>
      <ErrorText error={accept.error ?? reject.error} />
    </li>
  );
}

export function FollowupRowView({ f }: { f: FollowupRow }) {
  const refresh = useRefresh();
  const [answer, setAnswer] = useState("");
  const send = useMutation({
    mutationFn: () => post(`/followups/${f.id}/answer`, { answer }),
    onSuccess: () => {
      refresh();
      setTimeout(refresh, 3000);
    },
  });
  const dismiss = useMutation({ mutationFn: () => post(`/followups/${f.id}/dismiss`), onSuccess: refresh });
  return (
    <li className="rounded-xl bg-cream/70 p-3 text-sm">
      <p className="flex gap-2 font-medium">
        <MessageCircleQuestion size={16} className="mt-0.5 shrink-0 text-accent-2" />
        {f.question}
      </p>
      <div className="mt-2 flex gap-2">
        <input className="input py-1.5" value={answer} onChange={(e) => setAnswer(e.target.value)} placeholder="짧게 답하면 경험에 덧붙인다." />
        <button className="btn btn-sm" disabled={!answer.trim() || send.isPending} onClick={() => send.mutate()}>
          답하기
        </button>
        <button className="btn btn-ghost btn-sm" onClick={() => dismiss.mutate()}>
          넘기기
        </button>
      </div>
    </li>
  );
}

/** 일기 하나에서 나온 경험 후보와 질문을 그 자리에서 처리한다. */
export function EntryReview({ entryId }: { entryId: string }) {
  const refresh = useRefresh();
  const { proposals, followups } = usePending();
  const mine = (proposals.data?.proposals ?? []).filter((p) => p.entry_id === entryId);
  const questions = (followups.data?.followups ?? []).filter((f) => f.entry_id === entryId);
  const all = useMutation({
    mutationFn: () => post("/proposals/bulk-accept", { ids: mine.map((p) => p.id) }),
    onSuccess: refresh,
  });
  if (!mine.length && !questions.length) return null;
  return (
    <div className="space-y-2 rounded-2xl bg-mint/40 p-3 ring-1 ring-accent/30">
      <div className="flex items-center gap-2 px-1">
        <p className="text-sm font-semibold text-deep">이 일기에서 찾은 경험 {mine.length}개</p>
        {mine.length > 1 && (
          <button className="btn btn-sm ml-auto" onClick={() => all.mutate()} disabled={all.isPending}>
            <CheckCheck size={14} /> 모두 추가
          </button>
        )}
      </div>
      <ul className="space-y-2">
        {mine.map((p) => (
          <ProposalRow key={p.id} p={p} />
        ))}
        {questions.map((f) => (
          <FollowupRowView key={f.id} f={f} />
        ))}
      </ul>
      <ErrorText error={all.error} />
    </div>
  );
}
