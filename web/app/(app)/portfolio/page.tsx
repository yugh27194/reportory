"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { ErrorText } from "@/components/ErrorText";
import { ItemForm } from "@/components/ItemForm";
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

  const params = new URLSearchParams({ status: "approved" });
  if (type) params.set("type", type);
  if (skill.trim()) params.set("skill", skill.trim());
  const items = useQuery({
    queryKey: ["items", type, skill.trim()],
    queryFn: () => api<{ items: Item[] }>(`/items?${params}`),
  });
  const create = useMutation({
    mutationFn: (v: unknown) => post("/items", v),
    onSuccess: () => {
      setAdding(false);
      qc.invalidateQueries({ queryKey: ["items"] });
    },
  });

  const filtered = (items.data?.items ?? []).filter((i) => {
    if (visibility && i.visibility !== visibility) return false;
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
    <div className="space-y-5">
      <div className="flex flex-wrap items-end gap-2">
        <h1 className="mr-auto text-lg font-semibold">포트폴리오</h1>
        <select className="input w-auto" value={type} onChange={(e) => setType(e.target.value as ItemType | "")}>
          <option value="">모든 유형</option>
          {ITEM_TYPE_ORDER.map((t) => (
            <option key={t} value={t}>
              {ITEM_TYPE_LABELS[t]}
            </option>
          ))}
        </select>
        <input className="input w-32" placeholder="기술" value={skill} onChange={(e) => setSkill(e.target.value)} />
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
          <option value="">공개·비공개</option>
          <option value="public">공개</option>
          <option value="private">비공개</option>
        </select>
        <button className="btn btn-primary" onClick={() => setAdding((v) => !v)}>
          직접 추가
        </button>
      </div>

      {adding && (
        <div className="card">
          <ItemForm submitLabel="추가" busy={create.isPending} onSubmit={(v) => create.mutate(v)} />
          <ErrorText error={create.error} />
        </div>
      )}

      <ErrorText error={items.error} />
      {items.isSuccess && groups.length === 0 && (
        <p className="text-sm text-zinc-500">
          아직 승인한 항목이 없다. 일기를 쓰고 검토 큐에서 제안을 승인하면 여기에 쌓인다.
        </p>
      )}
      {groups.map((g) => (
        <section key={g.type} className="space-y-2">
          <h2 className="text-sm font-semibold text-zinc-500">{ITEM_TYPE_LABELS[g.type]}</h2>
          <div className="grid gap-2 sm:grid-cols-2">
            {g.items.map((i) => (
              <Link key={i.id} href={`/portfolio/${i.id}`} className="card block hover:border-brand">
                <div className="flex items-start gap-2">
                  <p className="font-medium">{i.title}</p>
                  {i.visibility === "public" && <span className="chip ml-auto shrink-0">공개</span>}
                </div>
                <p className="text-sm text-zinc-500">
                  {[i.organization, formatPeriod(i.start_date, i.end_date, i.is_ongoing)].filter(Boolean).join(" · ")}
                </p>
                {!!i.skills?.length && (
                  <div className="mt-2 flex flex-wrap gap-1">
                    {i.skills.map((s) => (
                      <span key={s} className="chip">
                        {s}
                      </span>
                    ))}
                  </div>
                )}
                <p className="mt-2 text-xs text-zinc-400">근거 {i.source_count ?? 0}건</p>
              </Link>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
