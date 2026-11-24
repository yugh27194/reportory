"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Archive,
  ArrowLeft,
  Download,
  Eye,
  EyeOff,
  FileUp,
  Globe,
  GitMerge,
  Lock,
  Paperclip,
  Pencil,
  Quote,
  Trash2,
} from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { ErrorText } from "@/components/ErrorText";
import { ItemForm, type ItemFormValues } from "@/components/ItemForm";
import { Spinner, TypeIcon } from "@/components/ui";
import { api, del, patch, post, upload } from "@/lib/api";
import { formatPeriod } from "@/lib/text";
import {
  DETAIL_LABELS,
  EVIDENCE_KIND_LABELS,
  ITEM_TYPE_LABELS,
  type Evidence,
  type Item,
  type ItemDetail,
} from "@/lib/types";

function sourceLabel(s: ItemDetail["sources"][number]) {
  if (s.entry_id) return `${s.entry_date ?? ""} 일기`;
  if (s.followup_id) return "후속 질문 답변";
  if (s.evidence_id) return "증빙";
  if (s.import_id) return "가져오기·직접 입력";
  return "근거";
}

function EvidenceRow({ ev, onChange }: { ev: Evidence; onChange: () => void }) {
  const open = useMutation({
    mutationFn: (download: boolean) => api<{ url: string }>(`/evidence/${ev.id}/url?download=${download}`),
    onSuccess: (r) => window.open(r.url, "_blank", "noopener"),
  });
  const vis = useMutation({
    mutationFn: () => patch(`/evidence/${ev.id}`, { visibility: ev.visibility === "public" ? "private" : "public" }),
    onSuccess: onChange,
  });
  const remove = useMutation({ mutationFn: () => del(`/evidence/${ev.id}`), onSuccess: onChange });
  const x = ev.extracted as { score?: string; title?: string; expires_on_estimated?: boolean };
  return (
    <li className="flex flex-wrap items-center gap-3 py-3">
      <span className="inline-flex h-9 w-9 items-center justify-center rounded-xl bg-cream text-deep">
        <Paperclip size={16} />
      </span>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium">{ev.file_name}</p>
        <p className="text-xs text-muted">
          {ev.status === "uploaded" ? (
            <Spinner label="읽는 중이다" />
          ) : (
            [
              ev.kind ? EVIDENCE_KIND_LABELS[ev.kind] : null,
              x.score ? `점수 ${x.score}` : null,
              ev.issued_on ? `발급 ${ev.issued_on}` : null,
              ev.expires_on ? `만료 ${ev.expires_on}${x.expires_on_estimated ? "(추정)" : ""}` : null,
            ]
              .filter(Boolean)
              .join(" · ")
          )}
        </p>
      </div>
      <div className="flex gap-1">
        <button className="btn btn-ghost btn-sm" onClick={() => open.mutate(false)} title="미리보기">
          <Eye size={14} />
        </button>
        <button className="btn btn-ghost btn-sm" onClick={() => open.mutate(true)} title="다운로드">
          <Download size={14} />
        </button>
        <button className="btn btn-ghost btn-sm" onClick={() => vis.mutate()} title="공개 설정">
          {ev.visibility === "public" ? <Globe size={14} className="text-accent-2" /> : <Lock size={14} />}
        </button>
        <button
          className="btn btn-ghost btn-sm hover:text-red-700"
          title="삭제"
          onClick={() => confirm("증빙 파일을 지운다. 되돌릴 수 없다.") && remove.mutate()}
        >
          <Trash2 size={14} />
        </button>
      </div>
      <ErrorText error={open.error ?? vis.error ?? remove.error} />
    </li>
  );
}

export default function ItemPage() {
  const { itemId } = useParams<{ itemId: string }>();
  const router = useRouter();
  const qc = useQueryClient();
  const fileRef = useRef<HTMLInputElement>(null);
  const [editing, setEditing] = useState(false);
  const [mergeTarget, setMergeTarget] = useState("");

  const item = useQuery({
    queryKey: ["item", itemId],
    queryFn: () => api<ItemDetail>(`/items/${itemId}`),
    refetchInterval: (q) => (q.state.data?.evidence.some((e) => e.status === "uploaded") ? 3000 : false),
  });
  const siblings = useQuery({
    queryKey: ["items", "approved"],
    queryFn: () => api<{ items: Item[] }>("/items?status=approved"),
    enabled: !!item.data,
  });
  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["item", itemId] });
    qc.invalidateQueries({ queryKey: ["items"] });
    qc.invalidateQueries({ queryKey: ["pending-count"] });
  };
  const save = useMutation({
    mutationFn: (v: ItemFormValues) => {
      const { type: _type, ...rest } = v;
      void _type;
      return patch(`/items/${itemId}`, rest);
    },
    onSuccess: () => {
      setEditing(false);
      refresh();
    },
  });
  const toggleVisibility = useMutation({
    mutationFn: () => patch(`/items/${itemId}`, { visibility: item.data?.visibility === "public" ? "private" : "public" }),
    onSuccess: refresh,
  });
  const archive = useMutation({
    mutationFn: () => api(`/items/${itemId}`, { method: "DELETE" }),
    onSuccess: () => {
      refresh();
      router.push("/portfolio");
    },
  });
  const merge = useMutation({
    mutationFn: () => post("/items/merge", { keep_item_id: itemId, merge_item_ids: [mergeTarget] }),
    onSuccess: () => {
      setMergeTarget("");
      refresh();
    },
  });
  const uploadEv = useMutation({
    mutationFn: (f: File) => upload(`/evidence`, f, { item_id: itemId }),
    onSuccess: refresh,
  });

  if (item.error) return <ErrorText error={item.error} />;
  const d = item.data;
  if (!d) return <Spinner label="불러오는 중이다" />;
  const others = siblings.data?.items.filter((i) => i.id !== d.id && i.type === d.type) ?? [];

  return (
    <div className="space-y-6">
      <Link href="/portfolio" className="inline-flex items-center gap-1 text-sm text-muted hover:text-ink">
        <ArrowLeft size={14} /> 모아보기
      </Link>

      <header className="card flex flex-wrap items-start gap-4">
        <TypeIcon type={d.type} size="lg" />
        <div className="min-w-0 flex-1">
          <p className="text-xs font-semibold text-muted">{ITEM_TYPE_LABELS[d.type]}</p>
          <h1 className="text-2xl font-bold tracking-tight">{d.title}</h1>
          {d.title_en && <p className="text-sm text-muted">{d.title_en}</p>}
          <p className="mt-1 text-sm text-muted">
            {[d.organization, d.role, formatPeriod(d.start_date, d.end_date, d.is_ongoing)].filter(Boolean).join(" · ")}
          </p>
          {d.status !== "approved" && <span className="chip chip-cream mt-2">아직 승인 전이다</span>}
        </div>
        <div className="flex flex-wrap gap-2">
          <button className="btn" onClick={() => setEditing((v) => !v)}>
            <Pencil size={14} /> 편집
          </button>
          <button className="btn" onClick={() => toggleVisibility.mutate()} disabled={toggleVisibility.isPending}>
            {d.visibility === "public" ? (
              <>
                <Globe size={14} className="text-accent-2" /> 공개 중
              </>
            ) : (
              <>
                <EyeOff size={14} /> 비공개
              </>
            )}
          </button>
          <button
            className="btn btn-ghost btn-danger"
            onClick={() => confirm("이 항목을 보관함으로 옮긴다. 포트폴리오와 공개 프로필에서 빠진다.") && archive.mutate()}
          >
            <Archive size={14} /> 보관
          </button>
        </div>
      </header>
      <ErrorText error={toggleVisibility.error ?? archive.error} />

      <div className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
        <div className="space-y-6">
          {editing ? (
            <section className="card">
              <ItemForm initial={d} allowTypeChange={false} submitLabel="저장" busy={save.isPending} onSubmit={(v) => save.mutate(v)} />
              <button className="mt-3 text-sm text-muted" onClick={() => setEditing(false)}>
                취소
              </button>
              <ErrorText error={save.error} />
            </section>
          ) : (
            <section className="card space-y-4">
              <h2 className="section-title">내용</h2>
              {d.summary ? (
                <p className="text-[15px] leading-relaxed whitespace-pre-wrap">{d.summary}</p>
              ) : (
                <p className="text-sm text-muted">요약이 아직 없다. 편집에서 쓰거나, 관련 일기를 쓰면 제안으로 채워진다.</p>
              )}
              {d.metrics.length > 0 && (
                <div className="flex flex-wrap gap-2">
                  {d.metrics.map((m) => (
                    <div key={m.name} className="rounded-xl bg-cream px-3 py-2">
                      <p className="text-lg font-bold text-deep">
                        {m.value}
                        {m.unit ?? ""}
                      </p>
                      <p className="text-xs text-muted">{m.name}</p>
                    </div>
                  ))}
                </div>
              )}
              {d.skills.length > 0 && (
                <div className="flex flex-wrap gap-1">
                  {d.skills.map((s) => (
                    <span key={s} className="chip">
                      {s}
                    </span>
                  ))}
                </div>
              )}
              {Object.keys(d.details).length > 0 && (
                <dl className="grid grid-cols-[100px_1fr] gap-x-3 gap-y-1.5 text-sm">
                  {Object.entries(d.details).map(([k, v]) => (
                    <div key={k} className="contents">
                      <dt className="text-muted">{DETAIL_LABELS[k] ?? k}</dt>
                      <dd className="break-all">
                        {typeof v === "string" && /^https?:\/\//.test(v) ? (
                          <a className="text-deep underline" href={v} target="_blank" rel="noopener noreferrer">
                            {v}
                          </a>
                        ) : (
                          String(v)
                        )}
                      </dd>
                    </div>
                  ))}
                </dl>
              )}
            </section>
          )}

          <section className="card">
            <h2 className="section-title mb-3 flex items-center gap-2">
              <Quote size={14} /> 근거 {d.sources.length}건
            </h2>
            {d.sources.length === 0 && <p className="text-sm text-muted">연결된 근거가 없다.</p>}
            <ul className="space-y-2">
              {d.sources.map((s) => (
                <li key={s.id} className="rounded-xl border-l-3 border-accent bg-cream/50 px-3 py-2 text-sm">
                  <p className="text-xs text-muted">{sourceLabel(s)}</p>
                  {s.quote && <p className="mt-0.5">“{s.quote}”</p>}
                </li>
              ))}
            </ul>
          </section>
        </div>

        <div className="space-y-6">
          <section className="card">
            <div className="mb-2 flex items-center">
              <h2 className="section-title flex items-center gap-2">
                <Paperclip size={14} /> 증빙
              </h2>
              <button className="btn btn-sm ml-auto" onClick={() => fileRef.current?.click()} disabled={uploadEv.isPending}>
                <FileUp size={14} /> {uploadEv.isPending ? "올리는 중이다" : "올리기"}
              </button>
              <input
                ref={fileRef}
                type="file"
                accept=".pdf,.png,.jpg,.jpeg,.webp"
                className="hidden"
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) uploadEv.mutate(f);
                  e.target.value = "";
                }}
              />
            </div>
            <p className="text-xs text-muted">성적표, 자격증, 상장, 수료증(PDF·PNG·JPG·WEBP, 10MB 이하)을 올리면 읽어서 값을 확인해 준다.</p>
            <ErrorText error={uploadEv.error} />
            {d.evidence.length > 0 && (
              <ul className="mt-2 divide-y divide-line/70">
                {d.evidence.map((ev) => (
                  <EvidenceRow key={ev.id} ev={ev} onChange={refresh} />
                ))}
              </ul>
            )}
          </section>

          {d.applications.length > 0 && (
            <section className="card">
              <h2 className="section-title mb-2">연결된 지원</h2>
              <ul className="text-sm">
                {d.applications.map((a) => (
                  <li key={a.id}>
                    {a.title} <span className="chip">{a.status}</span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {others.length > 0 && (
            <section className="card space-y-3">
              <h2 className="section-title flex items-center gap-2">
                <GitMerge size={14} /> 같은 기록 합치기
              </h2>
              <p className="text-xs text-muted">고른 항목의 근거·기술·증빙이 이 항목으로 옮겨지고, 고른 항목은 보관된다.</p>
              <select className="input" value={mergeTarget} onChange={(e) => setMergeTarget(e.target.value)}>
                <option value="">합칠 항목 고르기</option>
                {others.map((o) => (
                  <option key={o.id} value={o.id}>
                    {o.title}
                  </option>
                ))}
              </select>
              <button className="btn w-full" disabled={!mergeTarget || merge.isPending} onClick={() => merge.mutate()}>
                합치기
              </button>
              <ErrorText error={merge.error} />
            </section>
          )}
        </div>
      </div>
    </div>
  );
}
