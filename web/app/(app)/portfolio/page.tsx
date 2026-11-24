"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Globe, LayoutGrid, Paperclip, Plus, Quote, Search, X } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { ErrorText } from "@/components/ErrorText";
import { ItemForm } from "@/components/ItemForm";
import { EmptyState, PageHeader, TypeIcon } from "@/components/ui";
import { api, post } from "@/lib/api";
import { formatPeriod } from "@/lib/text";
import { ITEM_TYPE_LABELS, ITEM_TYPE_ORDER, type Item, type ItemType } from "@/lib/types";

export default function PortfolioPage() {
  const qc = useQueryClient();
  const [type, setType] = useState<ItemType | "">("");
  const [skill, setSkill] = useState("");
  const [visibility, setVisibility] = useState<"" | "public" | "private">("");
  const [year, setYear] = useState("");
  const [adding, setAdding] = useState(false);

  const items = useQuery({
    queryKey: ["items", "approved"],
    queryFn: () => api<{ items: Item[] }>("/items?status=approved"),
  });
  const create = useMutation({
    mutationFn: (v: unknown) => post("/items", v),
    onSuccess: () => {
      setAdding(false);
      qc.invalidateQueries({ queryKey: ["items"] });
      qc.invalidateQueries({ queryKey: ["stats"] });
    },
  });

  const all = items.data?.items ?? [];
  const counts = Object.fromEntries(ITEM_TYPE_ORDER.map((t) => [t, all.filter((i) => i.type === t).length]));
  const q = skill.trim().toLowerCase();
  const filtered = all.filter((i) => {
    if (type && i.type !== type) return false;
    if (visibility && i.visibility !== visibility) return false;
    if (q && !(i.skills ?? []).some((s) => s.toLowerCase().includes(q)) && !i.title.toLowerCase().includes(q)) return false;
    if (year) {
      const from = i.start_date?.slice(0, 4) ?? i.end_date?.slice(0, 4);
      const to = i.is_ongoing ? "9999" : (i.end_date?.slice(0, 4) ?? from);
      if (!from || !to || year < from || year > to) return false;
    }
    return true;
  });
  const groups = ITEM_TYPE_ORDER.map((t) => ({ type: t, items: filtered.filter((i) => i.type === t) })).filter(
    (g) => g.items.length > 0,
  );

  return (
    <div>
      <PageHeader
        eyebrow="Portfolio"
        title="포트폴리오"
        description={`승인한 항목 ${all.length}개. 공개로 표시한 항목만 공개 프로필에 보인다.`}
        actions={
          <button className="btn btn-primary" onClick={() => setAdding((v) => !v)}>
            {adding ? <X size={16} /> : <Plus size={16} />} {adding ? "닫기" : "직접 추가"}
          </button>
        }
      />

      {adding && (
        <div className="card mb-6">
          <p className="mb-4 font-semibold">항목 직접 추가</p>
          <ItemForm submitLabel="추가" busy={create.isPending} onSubmit={(v) => create.mutate(v)} />
          <ErrorText error={create.error} />
        </div>
      )}

      <div className="mb-6 space-y-3">
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => setType("")}
            className={`rounded-full px-3.5 py-1.5 text-sm ${type === "" ? "bg-ink text-white" : "bg-white text-muted ring-1 ring-line hover:text-ink"}`}
          >
            전체 {all.length}
          </button>
          {ITEM_TYPE_ORDER.filter((t) => counts[t] > 0).map((t) => (
            <button
              key={t}
              onClick={() => setType(type === t ? "" : t)}
              className={`rounded-full px-3.5 py-1.5 text-sm ${type === t ? "bg-ink text-white" : "bg-white text-muted ring-1 ring-line hover:text-ink"}`}
            >
              {ITEM_TYPE_LABELS[t]} {counts[t]}
            </button>
          ))}
        </div>
        <div className="flex flex-wrap gap-2">
          <div className="relative">
            <Search size={16} className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-muted" />
            <input className="input w-56 pl-9" placeholder="제목·기술 검색" value={skill} onChange={(e) => setSkill(e.target.value)} />
          </div>
          <input
            className="input w-24"
            placeholder="연도"
            inputMode="numeric"
            maxLength={4}
            value={year}
            onChange={(e) => setYear(e.target.value.replace(/\D/g, ""))}
          />
          <select
            className="input w-auto"
            value={visibility}
            onChange={(e) => setVisibility(e.target.value as "" | "public" | "private")}
          >
            <option value="">공개·비공개 모두</option>
            <option value="public">공개만</option>
            <option value="private">비공개만</option>
          </select>
        </div>
      </div>

      <ErrorText error={items.error} />
      {items.isSuccess && all.length === 0 && (
        <EmptyState
          icon={LayoutGrid}
          title="아직 승인한 항목이 없다"
          description="일기를 쓰고 검토 큐에서 제안을 승인하거나, 처음 설정에서 이력서·GitHub를 가져와 보세요."
          action={
            <Link href="/onboarding" className="btn btn-primary">
              기록 가져오기
            </Link>
          }
        />
      )}
      {items.isSuccess && all.length > 0 && groups.length === 0 && (
        <p className="text-sm text-muted">조건에 맞는 항목이 없다.</p>
      )}
      <div className="space-y-8">
        {groups.map((g) => (
          <section key={g.type}>
            <h2 className="section-title mb-3 flex items-center gap-2">
              {ITEM_TYPE_LABELS[g.type]} <span className="text-muted">{g.items.length}</span>
            </h2>
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
              {g.items.map((i) => (
                <Link key={i.id} href={`/portfolio/${i.id}`} className="card card-hover flex flex-col gap-3 p-4">
                  <div className="flex items-start gap-3">
                    <TypeIcon type={i.type} />
                    <div className="min-w-0 flex-1">
                      <p className="leading-snug font-semibold">{i.title}</p>
                      <p className="mt-0.5 text-xs text-muted">
                        {[i.organization, formatPeriod(i.start_date, i.end_date, i.is_ongoing)].filter(Boolean).join(" · ")}
                      </p>
                    </div>
                    {i.visibility === "public" && <Globe size={15} className="shrink-0 text-accent-2" aria-label="공개" />}
                  </div>
                  {i.summary && <p className="line-clamp-2 text-sm text-muted">{i.summary}</p>}
                  {!!i.skills?.length && (
                    <div className="flex flex-wrap gap-1">
                      {i.skills.slice(0, 5).map((s) => (
                        <span key={s} className="chip">
                          {s}
                        </span>
                      ))}
                      {i.skills.length > 5 && <span className="chip chip-cream">+{i.skills.length - 5}</span>}
                    </div>
                  )}
                  <div className="mt-auto flex gap-3 text-xs text-muted">
                    <span className="inline-flex items-center gap-1">
                      <Quote size={12} /> 근거 {i.source_count ?? 0}
                    </span>
                    {!!i.evidence_count && (
                      <span className="inline-flex items-center gap-1">
                        <Paperclip size={12} /> 증빙 {i.evidence_count}
                      </span>
                    )}
                  </div>
                </Link>
              ))}
            </div>
          </section>
        ))}
      </div>
    </div>
  );
}
