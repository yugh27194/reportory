"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { ErrorText } from "@/components/ErrorText";
import { ItemForm, type ItemFormValues } from "@/components/ItemForm";
import { api, patch, post } from "@/lib/api";
import { formatPeriod } from "@/lib/text";
import { DETAIL_LABELS, ITEM_TYPE_LABELS, type Item, type ItemDetail } from "@/lib/types";

function sourceLabel(s: ItemDetail["sources"][number]) {
  if (s.entry_id) return `${s.entry_date ?? ""} 일기`;
  if (s.followup_id) return "후속 질문 답변";
  if (s.import_id) return "직접 입력·가져오기";
  if (s.evidence_id) return "증빙";
  return "근거";
}

export default function ItemPage() {
  const { itemId } = useParams<{ itemId: string }>();
  const router = useRouter();
  const qc = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [mergeTarget, setMergeTarget] = useState("");

  const item = useQuery({ queryKey: ["item", itemId], queryFn: () => api<ItemDetail>(`/items/${itemId}`) });
  const siblings = useQuery({
    queryKey: ["items", item.data?.type],
    queryFn: () => api<{ items: Item[] }>(`/items?status=approved&type=${item.data!.type}`),
    enabled: !!item.data,
  });
  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["item", itemId] });
    qc.invalidateQueries({ queryKey: ["items"] });
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
    mutationFn: () =>
      patch(`/items/${itemId}`, { visibility: item.data?.visibility === "public" ? "private" : "public" }),
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

  if (item.error) return <ErrorText error={item.error} />;
  const d = item.data;
  if (!d) return null;
  const others = siblings.data?.items.filter((i) => i.id !== d.id) ?? [];

  return (
    <div className="space-y-5">
      <Link href="/portfolio" className="text-sm text-zinc-500">
        ‹ 포트폴리오
      </Link>
      <header className="space-y-1">
        <p className="text-sm text-zinc-500">{ITEM_TYPE_LABELS[d.type]}</p>
        <h1 className="text-xl font-semibold">{d.title}</h1>
        <p className="text-sm text-zinc-500">
          {[d.organization, d.role, formatPeriod(d.start_date, d.end_date, d.is_ongoing)].filter(Boolean).join(" · ")}
        </p>
        {d.status !== "approved" && <p className="chip">아직 승인 전이다</p>}
      </header>

      {editing ? (
        <div className="card">
          <ItemForm
            initial={d}
            allowTypeChange={false}
            submitLabel="저장"
            busy={save.isPending}
            onSubmit={(v) => save.mutate(v)}
          />
          <button className="mt-2 text-sm text-zinc-500" onClick={() => setEditing(false)}>
            취소
          </button>
          <ErrorText error={save.error} />
        </div>
      ) : (
        <section className="card space-y-3">
          {d.summary ? <p className="whitespace-pre-wrap text-sm leading-relaxed">{d.summary}</p> : (
            <p className="text-sm text-zinc-400">요약이 아직 없다.</p>
          )}
          {d.metrics.length > 0 && (
            <ul className="flex flex-wrap gap-2 text-sm">
              {d.metrics.map((m) => (
                <li key={m.name} className="chip">
                  {m.name} {m.value}
                  {m.unit ?? ""}
                </li>
              ))}
            </ul>
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
            <dl className="grid grid-cols-[100px_1fr] gap-1 text-sm">
              {Object.entries(d.details).map(([k, v]) => (
                <div key={k} className="contents">
                  <dt className="text-zinc-500">{DETAIL_LABELS[k] ?? k}</dt>
                  <dd>
                    {typeof v === "string" && /^https?:\/\//.test(v) ? (
                      <a className="text-brand underline" href={v} target="_blank" rel="noopener noreferrer">
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
          <div className="flex flex-wrap gap-2">
            <button className="btn" onClick={() => setEditing(true)}>
              편집
            </button>
            <button className="btn" onClick={() => toggleVisibility.mutate()} disabled={toggleVisibility.isPending}>
              {d.visibility === "public" ? "비공개로 바꾸기" : "공개로 바꾸기"}
            </button>
            <button
              className="btn btn-danger"
              onClick={() => {
                if (confirm("이 항목을 보관함으로 옮긴다. 포트폴리오와 공개 프로필에서 빠진다.")) archive.mutate();
              }}
            >
              보관
            </button>
          </div>
          <ErrorText error={toggleVisibility.error ?? archive.error} />
        </section>
      )}

      <section className="space-y-2">
        <h2 className="text-sm font-semibold text-zinc-500">근거 {d.sources.length}건</h2>
        {d.sources.length === 0 && <p className="text-sm text-zinc-400">연결된 근거가 없다.</p>}
        <ul className="space-y-2">
          {d.sources.map((s) => (
            <li key={s.id} className="card text-sm">
              <p className="text-xs text-zinc-400">{sourceLabel(s)}</p>
              {s.quote && <p className="mt-1">“{s.quote}”</p>}
            </li>
          ))}
        </ul>
      </section>

      {d.applications.length > 0 && (
        <section className="space-y-2">
          <h2 className="text-sm font-semibold text-zinc-500">연결된 지원</h2>
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
        <section className="card space-y-2">
          <h2 className="text-sm font-semibold">다른 항목을 이 항목에 합치기</h2>
          <p className="text-xs text-zinc-500">고른 항목의 근거와 기술이 이 항목으로 옮겨지고, 고른 항목은 보관된다.</p>
          <div className="flex gap-2">
            <select className="input" value={mergeTarget} onChange={(e) => setMergeTarget(e.target.value)}>
              <option value="">합칠 항목 고르기</option>
              {others.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.title}
                </option>
              ))}
            </select>
            <button className="btn" disabled={!mergeTarget || merge.isPending} onClick={() => merge.mutate()}>
              합치기
            </button>
          </div>
          <ErrorText error={merge.error} />
        </section>
      )}
    </div>
  );
}
