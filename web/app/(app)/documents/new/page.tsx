"use client";

import { useMutation } from "@tanstack/react-query";
import { ArrowDown, ArrowUp, Check, Sparkles } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { DocFormatIcon } from "@/components/DocFormatIcon";
import { ErrorText } from "@/components/ErrorText";
import { PageHeader, Spinner, TypeIcon } from "@/components/ui";
import { patch, post } from "@/lib/api";
import { formatPeriod } from "@/lib/text";
import { DOC_FORMATS, ITEM_TYPE_LABELS, type DocFormat, type DocumentRow, type RankedItem } from "@/lib/types";

function Step({ n, title, children, done }: { n: number; title: string; children: React.ReactNode; done?: boolean }) {
  return (
    <section className="card">
      <h2 className="mb-4 flex items-center gap-3 font-semibold">
        <span
          className={`inline-flex h-7 w-7 items-center justify-center rounded-full text-sm ${done ? "bg-deep text-white" : "bg-mint text-deep"}`}
        >
          {done ? <Check size={14} /> : n}
        </span>
        {title}
      </h2>
      {children}
    </section>
  );
}

function NewDocument() {
  const router = useRouter();
  const params = useSearchParams();
  const initial = (params.get("format") as DocFormat) || "resume_ko";
  const [format, setFormat] = useState<DocFormat>(initial);
  const [title, setTitle] = useState("");
  const [target, setTarget] = useState("");
  const [doc, setDoc] = useState<DocumentRow | null>(null);
  const [items, setItems] = useState<RankedItem[]>([]);
  const [titleEn, setTitleEn] = useState<Record<string, string>>({});

  const prepare = useMutation({
    mutationFn: async () => {
      const created =
        doc ??
        (await post<DocumentRow>("/documents", {
          format,
          title: title.trim() || DOC_FORMATS.find((f) => f.key === format)!.label,
          target_description: target.trim() || null,
        }));
      setDoc(created);
      const r = await post<{ items: RankedItem[] }>(`/documents/${created.id}/preview-selection`);
      setItems(r.items);
    },
  });
  const generate = useMutation({
    mutationFn: async () => {
      if (!doc) return;
      for (const [id, v] of Object.entries(titleEn)) {
        if (v.trim()) await patch(`/items/${id}`, { title_en: v.trim() });
      }
      await post(`/documents/${doc.id}/versions`, {
        selected_item_ids: items.filter((i) => i.selected).map((i) => i.id),
      });
      router.push(`/documents/${doc.id}`);
    },
  });

  const move = (idx: number, d: -1 | 1) =>
    setItems((list) => {
      const next = [...list];
      const j = idx + d;
      if (j < 0 || j >= next.length) return list;
      [next[idx], next[j]] = [next[j], next[idx]];
      return next;
    });
  const selected = items.filter((i) => i.selected);
  const missingEn = format === "resume_en" ? selected.filter((i) => !i.title_en && !titleEn[i.id]?.trim()) : [];

  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <PageHeader eyebrow="New document" title="새 문서 만들기" description="형식 → 지원 대상 → 항목 고르기 순서로 만든다." />

      <Step n={1} title="형식 고르기" done={!!doc}>
        <div className="grid gap-3 sm:grid-cols-2">
          {DOC_FORMATS.map((f) => (
            <button
              key={f.key}
              disabled={!!doc}
              onClick={() => setFormat(f.key)}
              className={`flex gap-3 rounded-2xl border p-4 text-left transition ${
                format === f.key ? "border-deep bg-mint/50 ring-2 ring-accent/50" : "border-line hover:border-deep/30"
              } disabled:cursor-default`}
            >
              <DocFormatIcon format={f.key} />
              <span>
                <span className="block font-semibold">{f.label}</span>
                <span className="mt-0.5 block text-xs leading-relaxed text-muted">{f.desc}</span>
              </span>
            </button>
          ))}
        </div>
      </Step>

      <Step n={2} title="어디에 낼 문서인가요" done={!!doc}>
        <div className="space-y-3">
          <label className="block">
            <span className="label">문서 이름</span>
            <input
              className="input"
              placeholder="예: OO전자 백엔드 인턴 지원"
              value={title}
              disabled={!!doc}
              onChange={(e) => setTitle(e.target.value)}
            />
          </label>
          <label className="block">
            <span className="label">지원 대상 설명(선택)</span>
            <textarea
              className="input min-h-24"
              placeholder="공고 내용이나 연구실 소개를 붙여 넣으면 관련 있는 항목을 앞에 둔다."
              value={target}
              disabled={!!doc}
              onChange={(e) => setTarget(e.target.value)}
            />
          </label>
          {!doc && (
            <button className="btn btn-primary" onClick={() => prepare.mutate()} disabled={prepare.isPending}>
              <Sparkles size={16} /> {prepare.isPending ? "항목을 고르는 중이다" : "넣을 항목 추천받기"}
            </button>
          )}
          <ErrorText error={prepare.error} />
        </div>
      </Step>

      {doc && (
        <Step n={3} title={`항목 고르기 · ${selected.length}개 선택`}>
          {items.length === 0 ? (
            <p className="text-sm text-muted">이 형식에 넣을 승인 항목이 없다. 먼저 포트폴리오를 채워 보세요.</p>
          ) : (
            <ul className="divide-y divide-line/70">
              {items.map((i, idx) => (
                <li key={i.id} className={`flex flex-wrap items-center gap-3 py-2.5 ${i.selected ? "" : "opacity-55"}`}>
                  <input
                    type="checkbox"
                    className="h-4 w-4 accent-[#224B46]"
                    checked={i.selected}
                    onChange={() =>
                      setItems((list) => list.map((x) => (x.id === i.id ? { ...x, selected: !x.selected } : x)))
                    }
                    aria-label={`${i.title} 넣기`}
                  />
                  <TypeIcon type={i.type} size="sm" />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium">{i.title}</p>
                    <p className="text-xs text-muted">
                      {ITEM_TYPE_LABELS[i.type]} · {formatPeriod(i.start_date, i.end_date, i.is_ongoing) || "기간 없음"}
                    </p>
                  </div>
                  <span className="hidden text-xs text-muted sm:inline">적합도 {Math.round(i.score * 100)}</span>
                  <span className="flex">
                    <button className="btn-ghost rounded p-1" onClick={() => move(idx, -1)} aria-label="위로">
                      <ArrowUp size={14} />
                    </button>
                    <button className="btn-ghost rounded p-1" onClick={() => move(idx, 1)} aria-label="아래로">
                      <ArrowDown size={14} />
                    </button>
                  </span>
                  {format === "resume_en" && i.selected && !i.title_en && (
                    <input
                      className="input mt-1 w-full sm:ml-14"
                      placeholder="영문 제목(이름·기관 표기를 지어내지 않도록 직접 넣는다)"
                      value={titleEn[i.id] ?? ""}
                      onChange={(e) => setTitleEn((m) => ({ ...m, [i.id]: e.target.value }))}
                    />
                  )}
                </li>
              ))}
            </ul>
          )}
          <div className="mt-5 flex flex-wrap items-center gap-3">
            <button
              className="btn btn-primary"
              disabled={selected.length === 0 || missingEn.length > 0 || generate.isPending}
              onClick={() => generate.mutate()}
            >
              {generate.isPending ? <Spinner label="만드는 중이다" /> : "문서 만들기"}
            </button>
            {missingEn.length > 0 && (
              <span className="text-sm text-amber-700">영문 제목이 없는 항목 {missingEn.length}개를 채워야 한다.</span>
            )}
          </div>
          <ErrorText error={generate.error} />
        </Step>
      )}
    </div>
  );
}

export default function NewDocumentPage() {
  return (
    <Suspense>
      <NewDocument />
    </Suspense>
  );
}
