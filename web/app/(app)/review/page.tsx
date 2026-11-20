"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { ErrorText } from "@/components/ErrorText";
import { api, post } from "@/lib/api";
import { formatPeriod, highlightQuote } from "@/lib/text";
import {
  ITEM_TYPE_LABELS,
  PROPOSAL_KIND_LABELS,
  detailText,
  type Followup,
  type Item,
  type Metric,
  type Proposal,
} from "@/lib/types";

const BULK_MIN = 0.8;

function Quote({ proposal }: { proposal: Proposal }) {
  const [open, setOpen] = useState(false);
  if (!proposal.quote) return null;
  return (
    <div className="text-sm">
      <button className="text-left text-zinc-600 hover:text-zinc-900" onClick={() => setOpen((v) => !v)}>
        <span className="mr-1 text-zinc-400">근거</span>“{proposal.quote}”
        {proposal.entry_body && <span className="ml-1 text-xs text-brand">{open ? "원문 닫기" : "원문 보기"}</span>}
      </button>
      {open && proposal.entry_body && (
        <p className="mt-2 whitespace-pre-wrap rounded bg-zinc-50 p-3 text-zinc-600">
          <span className="mb-1 block text-xs text-zinc-400">{proposal.entry_date} 일기</span>
          {highlightQuote(proposal.entry_body, proposal.quote).map((s, i) =>
            s.highlight ? (
              <mark key={i} className="bg-yellow-200">
                {s.text}
              </mark>
            ) : (
              <span key={i}>{s.text}</span>
            ),
          )}
        </p>
      )}
    </div>
  );
}

function Field({ label, before, after }: { label: string; before?: React.ReactNode; after: React.ReactNode }) {
  if (!after && !before) return null;
  return (
    <div className="grid grid-cols-[88px_1fr] gap-2 text-sm">
      <span className="text-zinc-500">{label}</span>
      <span>
        {before !== undefined && before !== after && (
          <span className="mr-2 text-zinc-400 line-through">{before || "없음"}</span>
        )}
        {after}
      </span>
    </div>
  );
}

const metricText = (ms: Metric[]) => ms.map((m) => `${m.name} ${m.value}${m.unit ?? ""}`).join(", ");

function Changes({ p }: { p: Proposal }) {
  const item = p.item;
  if (p.kind === "create_item" && item) {
    return (
      <div className="space-y-1">
        <Field label="유형" after={ITEM_TYPE_LABELS[item.type]} />
        <Field label="제목" after={item.title} />
        <Field label="기관" after={item.organization} />
        <Field label="역할" after={item.role} />
        <Field label="기간" after={formatPeriod(item.start_date, item.end_date, item.is_ongoing)} />
        <Field label="요약" after={item.summary} />
        <Field label="수치" after={metricText(item.metrics)} />
        <Field label="세부" after={detailText(item.details)} />
        <Field label="기술" after={p.item_skills.join(", ")} />
      </div>
    );
  }
  if (p.kind === "update_item" && item) {
    const patch = p.payload.patch as {
      summary_append?: string;
      end_date?: string | null;
      role?: string | null;
      metrics_add?: Metric[];
      skills_add?: string[];
      details_patch?: Record<string, unknown>;
    };
    return (
      <div className="space-y-1">
        <Field label="대상" after={`${ITEM_TYPE_LABELS[item.type]} · ${item.title}`} />
        {patch.summary_append && <Field label="요약 추가" after={patch.summary_append} />}
        {patch.role && <Field label="역할" before={item.role ?? ""} after={patch.role} />}
        {patch.end_date && <Field label="종료일" before={item.end_date ?? ""} after={patch.end_date} />}
        {!!patch.metrics_add?.length && (
          <Field label="수치" before={metricText(item.metrics)} after={metricText(patch.metrics_add)} />
        )}
        {!!patch.skills_add?.length && <Field label="기술 추가" after={patch.skills_add.join(", ")} />}
        {patch.details_patch && Object.keys(patch.details_patch).length > 0 && (
          <Field
            label="세부"
            after={detailText(patch.details_patch)}
          />
        )}
      </div>
    );
  }
  if (p.kind === "link_entry" && item) {
    return <Field label="연결할 항목" after={`${ITEM_TYPE_LABELS[item.type]} · ${item.title}`} />;
  }
  return <pre className="overflow-x-auto text-xs text-zinc-500">{JSON.stringify(p.payload, null, 2)}</pre>;
}

function EditForm({ item, onSubmit, busy }: { item: Item; onSubmit: (v: Record<string, unknown>) => void; busy: boolean }) {
  const [title, setTitle] = useState(item.title);
  const [organization, setOrganization] = useState(item.organization ?? "");
  const [role, setRole] = useState(item.role ?? "");
  const [startDate, setStartDate] = useState(item.start_date ?? "");
  const [endDate, setEndDate] = useState(item.end_date ?? "");
  const [summary, setSummary] = useState(item.summary);
  return (
    <form
      className="mt-3 grid gap-2 sm:grid-cols-2"
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit({
          title,
          organization: organization || null,
          role: role || null,
          start_date: startDate || null,
          end_date: endDate || null,
          summary,
        });
      }}
    >
      <label className="sm:col-span-2">
        <span className="label">제목</span>
        <input className="input" value={title} onChange={(e) => setTitle(e.target.value)} required />
      </label>
      <label>
        <span className="label">기관</span>
        <input className="input" value={organization} onChange={(e) => setOrganization(e.target.value)} />
      </label>
      <label>
        <span className="label">역할</span>
        <input className="input" value={role} onChange={(e) => setRole(e.target.value)} />
      </label>
      <label>
        <span className="label">시작일</span>
        <input type="date" className="input" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
      </label>
      <label>
        <span className="label">종료일</span>
        <input type="date" className="input" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
      </label>
      <label className="sm:col-span-2">
        <span className="label">요약</span>
        <textarea className="input min-h-20" value={summary} onChange={(e) => setSummary(e.target.value)} />
      </label>
      <div className="sm:col-span-2">
        <button className="btn btn-primary" disabled={busy}>
          수정한 내용으로 승인
        </button>
      </div>
    </form>
  );
}

function ProposalCard({
  p,
  selected,
  toggle,
}: {
  p: Proposal;
  selected: boolean;
  toggle: () => void;
}) {
  const qc = useQueryClient();
  const [editing, setEditing] = useState(false);
  const done = () => {
    qc.invalidateQueries({ queryKey: ["proposals"] });
    qc.invalidateQueries({ queryKey: ["followups"] });
    qc.invalidateQueries({ queryKey: ["pending-count"] });
    qc.invalidateQueries({ queryKey: ["items"] });
  };
  const accept = useMutation({
    mutationFn: (edited?: Record<string, unknown>) =>
      post(`/proposals/${p.id}/accept`, edited ? { edited_payload: edited } : undefined),
    onSuccess: done,
  });
  const reject = useMutation({ mutationFn: () => post(`/proposals/${p.id}/reject`), onSuccess: done });
  const mergeIntoDuplicate = useMutation({
    // 제안 항목의 근거·기술을 기존 항목으로 옮긴다. 제안은 서버에서 함께 거절 처리된다.
    mutationFn: () =>
      post("/items/merge", { keep_item_id: p.possible_duplicate_of, merge_item_ids: [p.item_id] }),
    onSuccess: done,
  });
  const busy = accept.isPending || reject.isPending || mergeIntoDuplicate.isPending;
  const bulkable = (p.confidence ?? 0) >= BULK_MIN;

  return (
    <article className="card space-y-3">
      <header className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={selected}
          onChange={toggle}
          disabled={!bulkable}
          aria-label="일괄 승인에 넣기"
          title={bulkable ? "일괄 승인에 넣기" : "신뢰도 0.8 미만은 하나씩 확인해야 한다"}
        />
        <span className="chip">{PROPOSAL_KIND_LABELS[p.kind]}</span>
        {p.confidence !== null && (
          <span className={`text-xs ${bulkable ? "text-zinc-500" : "text-amber-700"}`}>
            신뢰도 {Math.round(p.confidence * 100)}%
          </span>
        )}
        {p.entry_date && <span className="ml-auto text-xs text-zinc-400">{p.entry_date} 일기</span>}
      </header>
      <Changes p={p} />
      <Quote proposal={p} />
      {p.duplicate && (
        <p className="rounded bg-amber-50 p-2 text-sm text-amber-900">
          이미 있는 항목 “{p.duplicate.title}”과 같은 기록일 수 있다.
        </p>
      )}
      <div className="flex flex-wrap gap-2">
        <button className="btn btn-primary" onClick={() => accept.mutate(undefined)} disabled={busy}>
          승인
        </button>
        {p.kind === "create_item" && p.item && (
          <button className="btn" onClick={() => setEditing((v) => !v)} disabled={busy}>
            수정 후 승인
          </button>
        )}
        {p.duplicate && (
          <button className="btn" onClick={() => mergeIntoDuplicate.mutate()} disabled={busy}>
            기존 항목에 합치기
          </button>
        )}
        <button className="btn btn-danger" onClick={() => reject.mutate()} disabled={busy}>
          거절
        </button>
      </div>
      {editing && p.item && <EditForm item={p.item} busy={busy} onSubmit={(v) => accept.mutate(v)} />}
      <ErrorText error={accept.error ?? reject.error ?? mergeIntoDuplicate.error} />
    </article>
  );
}

function FollowupCard({ f }: { f: Followup }) {
  const qc = useQueryClient();
  const [answer, setAnswer] = useState("");
  const done = () => {
    qc.invalidateQueries({ queryKey: ["followups"] });
    qc.invalidateQueries({ queryKey: ["pending-count"] });
  };
  const send = useMutation({
    mutationFn: () => post(`/followups/${f.id}/answer`, { answer }),
    onSuccess: () => {
      done();
      // 답변 분석이 끝나면 새 제안이 생긴다.
      setTimeout(() => qc.invalidateQueries({ queryKey: ["proposals"] }), 4000);
    },
  });
  const dismiss = useMutation({ mutationFn: () => post(`/followups/${f.id}/dismiss`), onSuccess: done });
  return (
    <article className="card space-y-2">
      <p className="text-xs text-zinc-500">
        {ITEM_TYPE_LABELS[f.item_type]} · {f.item_title}
      </p>
      <p className="font-medium">{f.question}</p>
      <textarea
        className="input min-h-16"
        value={answer}
        onChange={(e) => setAnswer(e.target.value)}
        placeholder="답하면 항목 갱신 제안이 새로 생긴다."
      />
      <div className="flex gap-2">
        <button className="btn btn-primary" disabled={!answer.trim() || send.isPending} onClick={() => send.mutate()}>
          답하기
        </button>
        <button className="btn" disabled={dismiss.isPending} onClick={() => dismiss.mutate()}>
          넘기기
        </button>
      </div>
      <ErrorText error={send.error ?? dismiss.error} />
    </article>
  );
}

export default function ReviewPage() {
  const qc = useQueryClient();
  const [tab, setTab] = useState<"proposals" | "followups">("proposals");
  const [kind, setKind] = useState<string>("all");
  const [highOnly, setHighOnly] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const proposals = useQuery({
    queryKey: ["proposals"],
    queryFn: () => api<{ proposals: Proposal[] }>("/proposals?status=pending"),
  });
  const followups = useQuery({
    queryKey: ["followups"],
    queryFn: () => api<{ followups: Followup[] }>("/followups?status=open"),
  });
  const bulk = useMutation({
    mutationFn: () => post("/proposals/bulk-accept", { ids: [...selected] }),
    onSuccess: () => {
      setSelected(new Set());
      qc.invalidateQueries({ queryKey: ["proposals"] });
      qc.invalidateQueries({ queryKey: ["pending-count"] });
      qc.invalidateQueries({ queryKey: ["items"] });
    },
  });

  const list = (proposals.data?.proposals ?? []).filter(
    (p) => (kind === "all" || p.kind === kind) && (!highOnly || (p.confidence ?? 0) >= BULK_MIN),
  );
  const toggle = (id: string) =>
    setSelected((s) => {
      const next = new Set(s);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  return (
    <div className="space-y-4">
      <div className="flex gap-1 border-b border-zinc-200">
        {(
          [
            ["proposals", `제안 ${proposals.data?.proposals.length ?? ""}`],
            ["followups", `질문 ${followups.data?.followups.length ?? ""}`],
          ] as const
        ).map(([key, label]) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`-mb-px border-b-2 px-4 py-2 text-sm ${
              tab === key ? "border-brand font-medium text-brand" : "border-transparent text-zinc-500"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === "proposals" && (
        <>
          <div className="flex flex-wrap items-center gap-3 text-sm">
            <select className="input w-auto" value={kind} onChange={(e) => setKind(e.target.value)}>
              <option value="all">모든 종류</option>
              {Object.entries(PROPOSAL_KIND_LABELS).map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            </select>
            <label className="flex items-center gap-1">
              <input type="checkbox" checked={highOnly} onChange={(e) => setHighOnly(e.target.checked)} />
              신뢰도 80% 이상만
            </label>
            <button
              className="btn btn-primary ml-auto"
              disabled={selected.size === 0 || bulk.isPending}
              onClick={() => bulk.mutate()}
            >
              선택한 {selected.size}건 일괄 승인
            </button>
          </div>
          <ErrorText error={bulk.error ?? proposals.error} />
          {proposals.isSuccess && list.length === 0 && (
            <p className="text-sm text-zinc-500">검토할 제안이 없다. 일기를 쓰면 여기에 제안이 쌓인다.</p>
          )}
          {list.map((p) => (
            <ProposalCard key={p.id} p={p} selected={selected.has(p.id)} toggle={() => toggle(p.id)} />
          ))}
        </>
      )}

      {tab === "followups" && (
        <>
          <ErrorText error={followups.error} />
          {followups.isSuccess && followups.data.followups.length === 0 && (
            <p className="text-sm text-zinc-500">열린 질문이 없다.</p>
          )}
          {followups.data?.followups.map((f) => (
            <FollowupCard key={f.id} f={f} />
          ))}
        </>
      )}
    </div>
  );
}
