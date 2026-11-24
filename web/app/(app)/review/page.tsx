"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, ClipboardCheck, FileCheck2, GitMerge, MessageCircleQuestion, Pencil, X } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { ErrorText } from "@/components/ErrorText";
import { EmptyState, PageHeader, Tabs, TypeIcon } from "@/components/ui";
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

const SOURCE_LABELS: Record<string, string> = {
  resume_file: "이력서",
  github: "GitHub",
  linkedin_zip: "LinkedIn",
  manual: "직접 입력",
};

function sourceLabel(p: Proposal) {
  if (p.entry_date) return `${p.entry_date} 일기`;
  if (p.import_source) return SOURCE_LABELS[p.import_source] ?? "가져오기";
  if (p.evidence_file_name) return `증빙 · ${p.evidence_file_name}`;
  if (p.payload.followup_id) return "질문 답변";
  return "";
}

function Quote({ proposal }: { proposal: Proposal }) {
  const [open, setOpen] = useState(false);
  if (!proposal.quote) return null;
  return (
    <div className="text-sm">
      <button className="w-full rounded-xl border-l-3 border-accent bg-cream/60 px-3 py-2 text-left text-ink/80" onClick={() => setOpen((v) => !v)}>
        “{proposal.quote}”
        {proposal.entry_body && <span className="ml-2 text-xs font-medium text-deep">{open ? "원문 닫기" : "원문 보기"}</span>}
      </button>
      {open && proposal.entry_body && (
        <p className="mt-2 rounded-xl bg-paper p-3 leading-relaxed whitespace-pre-wrap text-muted ring-1 ring-line">
          {highlightQuote(proposal.entry_body, proposal.quote).map((s, i) =>
            s.highlight ? (
              <mark key={i} className="rounded bg-accent/40 px-0.5 text-ink">
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
    <div className="grid grid-cols-[84px_1fr] gap-2 text-sm">
      <span className="text-muted">{label}</span>
      <span>
        {before !== undefined && before !== after && (
          <span className="mr-2 text-muted line-through decoration-red-300">{before || "없음"}</span>
        )}
        {after}
      </span>
    </div>
  );
}

const metricText = (ms: Metric[]) => ms.map((m) => `${m.name} ${m.value}${m.unit ?? ""}`).join(", ");

type Conflict = { field: string; label: string; item_value: string; evidence_value: string };
type Fill = { field: string; label: string; evidence_value: string };

function Changes({
  p,
  resolutions,
  setResolution,
}: {
  p: Proposal;
  resolutions: Record<string, "item" | "evidence">;
  setResolution: (f: string, v: "item" | "evidence") => void;
}) {
  const item = p.item;
  if (p.kind === "create_item" && item) {
    return (
      <div className="space-y-1.5">
        <Field label="기관" after={item.organization} />
        <Field label="역할" after={item.role} />
        <Field label="기간" after={formatPeriod(item.start_date, item.end_date, item.is_ongoing)} />
        <Field label="요약" after={item.summary} />
        <Field label="수치" after={metricText(item.metrics)} />
        <Field label="세부" after={detailText(item.details)} />
        {p.item_skills.length > 0 && (
          <div className="grid grid-cols-[84px_1fr] gap-2 text-sm">
            <span className="text-muted">기술</span>
            <span className="flex flex-wrap gap-1">
              {p.item_skills.map((s) => (
                <span key={s} className="chip">
                  {s}
                </span>
              ))}
            </span>
          </div>
        )}
      </div>
    );
  }
  if (p.kind === "update_item" && item) {
    const patch = p.payload.patch as {
      summary_append?: string;
      summary_replace?: string;
      end_date?: string | null;
      role?: string | null;
      metrics_add?: Metric[];
      skills_add?: string[];
      details_patch?: Record<string, unknown>;
    };
    return (
      <div className="space-y-1.5">
        {patch.summary_append && <Field label="요약 추가" after={patch.summary_append} />}
        {patch.summary_replace && <Field label="새 요약" before={item.summary} after={patch.summary_replace} />}
        {patch.role && <Field label="역할" before={item.role ?? ""} after={patch.role} />}
        {patch.end_date && <Field label="종료일" before={item.end_date ?? ""} after={patch.end_date} />}
        {!!patch.metrics_add?.length && (
          <Field label="수치" before={metricText(item.metrics)} after={metricText(patch.metrics_add)} />
        )}
        {!!patch.skills_add?.length && <Field label="기술 추가" after={patch.skills_add.join(", ")} />}
        {patch.details_patch && Object.keys(patch.details_patch).length > 0 && (
          <Field label="세부" after={detailText(patch.details_patch)} />
        )}
      </div>
    );
  }
  if (p.kind === "link_entry") return <p className="text-sm text-muted">이 일기를 항목의 근거로 연결한다.</p>;
  if (p.kind === "attach_evidence") {
    const conflicts = (p.payload.conflicts as Conflict[]) ?? [];
    const fills = (p.payload.fills as Fill[]) ?? [];
    return (
      <div className="space-y-3 text-sm">
        <p className="text-muted">증빙 파일을 이 항목에 연결한다.</p>
        {fills.length > 0 && (
          <div>
            <p className="mb-1 text-xs font-semibold text-muted">비어 있던 값을 증빙으로 채운다</p>
            {fills.map((f) => (
              <Field key={f.field} label={f.label} after={<span className="font-medium text-deep">{f.evidence_value}</span>} />
            ))}
          </div>
        )}
        {conflicts.length > 0 && (
          <div className="space-y-2 rounded-xl bg-amber-50 p-3">
            <p className="text-xs font-semibold text-amber-900">값이 다르다. 남길 값을 고른다.</p>
            {conflicts.map((c) => (
              <div key={c.field} className="grid grid-cols-[84px_1fr] items-center gap-2">
                <span className="text-muted">{c.label}</span>
                <span className="flex flex-wrap gap-2">
                  {(["item", "evidence"] as const).map((side) => (
                    <label
                      key={side}
                      className={`cursor-pointer rounded-lg border px-2.5 py-1 ${
                        (resolutions[c.field] ?? "evidence") === side ? "border-deep bg-white font-medium" : "border-line bg-white/60"
                      }`}
                    >
                      <input
                        type="radio"
                        className="sr-only"
                        checked={(resolutions[c.field] ?? "evidence") === side}
                        onChange={() => setResolution(c.field, side)}
                      />
                      {side === "item" ? `지금 값 ${c.item_value}` : `증빙 값 ${c.evidence_value}`}
                    </label>
                  ))}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  }
  return <pre className="overflow-x-auto text-xs text-muted">{JSON.stringify(p.payload, null, 2)}</pre>;
}

function EditForm({ item, onSubmit, busy }: { item: Item; onSubmit: (v: Record<string, unknown>) => void; busy: boolean }) {
  const [v, setV] = useState({
    title: item.title,
    organization: item.organization ?? "",
    role: item.role ?? "",
    start_date: item.start_date ?? "",
    end_date: item.end_date ?? "",
    summary: item.summary,
  });
  const set = (k: keyof typeof v) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setV((s) => ({ ...s, [k]: e.target.value }));
  return (
    <form
      className="grid gap-3 rounded-xl bg-paper p-4 ring-1 ring-line sm:grid-cols-2"
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit({
          title: v.title,
          organization: v.organization || null,
          role: v.role || null,
          start_date: v.start_date || null,
          end_date: v.end_date || null,
          summary: v.summary,
        });
      }}
    >
      <label className="sm:col-span-2">
        <span className="label">제목</span>
        <input className="input" value={v.title} onChange={set("title")} required />
      </label>
      <label>
        <span className="label">기관</span>
        <input className="input" value={v.organization} onChange={set("organization")} />
      </label>
      <label>
        <span className="label">역할</span>
        <input className="input" value={v.role} onChange={set("role")} />
      </label>
      <label>
        <span className="label">시작일</span>
        <input type="date" className="input" value={v.start_date} onChange={set("start_date")} />
      </label>
      <label>
        <span className="label">종료일</span>
        <input type="date" className="input" value={v.end_date} onChange={set("end_date")} />
      </label>
      <label className="sm:col-span-2">
        <span className="label">요약</span>
        <textarea className="input min-h-20" value={v.summary} onChange={set("summary")} />
      </label>
      <div className="sm:col-span-2">
        <button className="btn btn-primary" disabled={busy}>
          수정한 내용으로 승인
        </button>
      </div>
    </form>
  );
}

function ProposalCard({ p, selected, toggle }: { p: Proposal; selected: boolean; toggle: () => void }) {
  const qc = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [resolutions, setResolutions] = useState<Record<string, "item" | "evidence">>({});
  const done = () => {
    ["proposals", "followups", "pending-count", "items", "stats"].forEach((k) => qc.invalidateQueries({ queryKey: [k] }));
  };
  const accept = useMutation({
    mutationFn: (edited?: Record<string, unknown>) =>
      post(`/proposals/${p.id}/accept`, edited ? { edited_payload: edited } : undefined),
    onSuccess: done,
  });
  const reject = useMutation({ mutationFn: () => post(`/proposals/${p.id}/reject`), onSuccess: done });
  const mergeIntoDuplicate = useMutation({
    mutationFn: () => post("/items/merge", { keep_item_id: p.possible_duplicate_of, merge_item_ids: [p.item_id] }),
    onSuccess: done,
  });
  const busy = accept.isPending || reject.isPending || mergeIntoDuplicate.isPending;
  const item = p.item;

  function approve() {
    if (p.kind === "attach_evidence") {
      const conflicts = (p.payload.conflicts as Conflict[]) ?? [];
      const res = Object.fromEntries(conflicts.map((c) => [c.field, resolutions[c.field] ?? "evidence"]));
      accept.mutate({ resolutions: res });
    } else accept.mutate(undefined);
  }

  return (
    <article className={`card space-y-4 ${selected ? "ring-2 ring-accent" : ""}`}>
      <header className="flex items-start gap-3">
        {item ? <TypeIcon type={item.type} /> : <span className="inline-flex h-9 w-9 items-center justify-center rounded-xl bg-mint text-deep"><FileCheck2 size={18} /></span>}
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <span className="chip">{PROPOSAL_KIND_LABELS[p.kind]}</span>
            {item && <span className="text-muted">{ITEM_TYPE_LABELS[item.type]}</span>}
          </div>
          <p className="mt-1 font-semibold">{item?.title ?? "증빙"}</p>
          <p className="text-xs text-muted">{sourceLabel(p)}</p>
        </div>
        <input
          type="checkbox"
          className="mt-1 h-4 w-4 accent-[#224B46]"
          checked={selected}
          onChange={toggle}
          aria-label="한꺼번에 승인할 항목으로 고르기"
        />
      </header>
      <Changes p={p} resolutions={resolutions} setResolution={(f, v) => setResolutions((r) => ({ ...r, [f]: v }))} />
      <Quote proposal={p} />
      {p.duplicate && (
        <p className="flex items-center gap-2 rounded-xl bg-amber-50 p-3 text-sm text-amber-900">
          <GitMerge size={16} /> 이미 있는 항목 “{p.duplicate.title}”과 같은 기록일 수 있다.
        </p>
      )}
      <div className="flex flex-wrap gap-2">
        <button className="btn btn-primary" onClick={approve} disabled={busy}>
          <Check size={16} /> 승인
        </button>
        {p.kind === "create_item" && item && (
          <button className="btn" onClick={() => setEditing((v) => !v)} disabled={busy}>
            <Pencil size={14} /> 수정 후 승인
          </button>
        )}
        {p.duplicate && (
          <button className="btn" onClick={() => mergeIntoDuplicate.mutate()} disabled={busy}>
            <GitMerge size={14} /> 기존 항목에 합치기
          </button>
        )}
        <button className="btn btn-ghost btn-danger ml-auto" onClick={() => reject.mutate()} disabled={busy}>
          <X size={16} /> 거절
        </button>
      </div>
      {editing && item && <EditForm item={item} busy={busy} onSubmit={(v) => accept.mutate(v)} />}
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
      setTimeout(() => qc.invalidateQueries({ queryKey: ["proposals"] }), 4000);
    },
  });
  const dismiss = useMutation({ mutationFn: () => post(`/followups/${f.id}/dismiss`), onSuccess: done });
  return (
    <article className="card space-y-3">
      <div className="flex items-center gap-3">
        <TypeIcon type={f.item_type} size="sm" />
        <Link href={`/portfolio/${f.item_id}`} className="text-sm text-muted hover:text-deep">
          {f.item_title}
        </Link>
      </div>
      <p className="flex gap-2 font-semibold">
        <MessageCircleQuestion size={18} className="mt-0.5 shrink-0 text-accent-2" /> {f.question}
      </p>
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
        <button className="btn btn-ghost" disabled={dismiss.isPending} onClick={() => dismiss.mutate()}>
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
      ["proposals", "pending-count", "items", "stats"].forEach((k) => qc.invalidateQueries({ queryKey: [k] }));
    },
  });

  const all = proposals.data?.proposals ?? [];
  const list = all.filter((p) => kind === "all" || p.kind === kind);
  const toggle = (id: string) =>
    setSelected((s) => {
      const next = new Set(s);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  const kinds = [...new Set(all.map((p) => p.kind))];

  return (
    <div>
      <PageHeader
        eyebrow="To review"
        title="확인할 항목"
        description="이력서·GitHub·증빙에서 찾은 후보와 아직 고르지 않은 일기 후보를 모아 보여 준다. 일기 후보는 일기 화면에서도 바로 고를 수 있다."
        actions={
          <Tabs
            value={tab}
            onChange={setTab}
            tabs={[
              { key: "proposals", label: `제안 ${all.length}` },
              { key: "followups", label: `질문 ${followups.data?.followups.length ?? 0}` },
            ]}
          />
        }
      />

      {tab === "proposals" && (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-2 rounded-2xl bg-white/70 p-2 ring-1 ring-line">
            {["all", ...kinds].map((k) => (
              <button
                key={k}
                onClick={() => setKind(k)}
                className={`rounded-lg px-3 py-1.5 text-sm ${kind === k ? "bg-ink text-white" : "text-muted hover:bg-ink/5"}`}
              >
                {k === "all" ? "전체" : PROPOSAL_KIND_LABELS[k as Proposal["kind"]]}
              </button>
            ))}
            <div className="ml-auto flex gap-2">
              {list.length > 0 && (
                <button className="btn btn-sm" onClick={() => setSelected(new Set(list.map((p) => p.id)))}>
                  모두 선택({list.length})
                </button>
              )}
              <button className="btn btn-primary btn-sm" disabled={selected.size === 0 || bulk.isPending} onClick={() => bulk.mutate()}>
                선택한 {selected.size}건 승인
              </button>
            </div>
          </div>
          <ErrorText error={bulk.error ?? proposals.error} />
          {proposals.isSuccess && list.length === 0 && (
            <EmptyState
              icon={ClipboardCheck}
              title="검토할 제안이 없다"
              description="일기를 쓰거나 이력서·증빙을 올리면 여기에 제안이 쌓인다."
              action={
                <Link href="/journal" className="btn btn-primary">
                  일기 쓰러 가기
                </Link>
              }
            />
          )}
          <div className="grid gap-4 xl:grid-cols-2">
            {list.map((p) => (
              <ProposalCard key={p.id} p={p} selected={selected.has(p.id)} toggle={() => toggle(p.id)} />
            ))}
          </div>
        </div>
      )}

      {tab === "followups" && (
        <div className="space-y-4">
          <ErrorText error={followups.error} />
          {followups.isSuccess && followups.data.followups.length === 0 && (
            <EmptyState icon={MessageCircleQuestion} title="열린 질문이 없다" description="빠진 수치나 역할이 있으면 여기서 물어본다." />
          )}
          <div className="grid gap-4 xl:grid-cols-2">
            {followups.data?.followups.map((f) => (
              <FollowupCard key={f.id} f={f} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
