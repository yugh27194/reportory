"use client";

import { useState } from "react";
import { ITEM_TYPE_LABELS, ITEM_TYPE_ORDER, type Item, type ItemType } from "@/lib/types";

export type ItemFormValues = {
  type: ItemType;
  title: string;
  title_en: string | null;
  organization: string | null;
  role: string | null;
  start_date: string | null;
  end_date: string | null;
  is_ongoing: boolean;
  summary: string;
  skills: string[];
  visibility: "private" | "public";
};

export function ItemForm({
  initial,
  submitLabel,
  busy,
  onSubmit,
  allowTypeChange = true,
}: {
  initial?: Partial<Item> & { skills?: string[] };
  submitLabel: string;
  busy: boolean;
  onSubmit: (v: ItemFormValues) => void;
  allowTypeChange?: boolean;
}) {
  const [v, setV] = useState({
    type: (initial?.type ?? "project") as ItemType,
    title: initial?.title ?? "",
    title_en: initial?.title_en ?? "",
    organization: initial?.organization ?? "",
    role: initial?.role ?? "",
    start_date: initial?.start_date ?? "",
    end_date: initial?.end_date ?? "",
    is_ongoing: initial?.is_ongoing ?? false,
    summary: initial?.summary ?? "",
    skills: (initial?.skills ?? []).join(", "),
    visibility: initial?.visibility ?? "private",
  });
  const set = <K extends keyof typeof v>(k: K, value: (typeof v)[K]) => setV((s) => ({ ...s, [k]: value }));

  return (
    <form
      className="grid gap-3 sm:grid-cols-2"
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit({
          type: v.type,
          title: v.title.trim(),
          title_en: v.title_en.trim() || null,
          organization: v.organization.trim() || null,
          role: v.role.trim() || null,
          start_date: v.start_date || null,
          end_date: v.is_ongoing ? null : v.end_date || null,
          is_ongoing: v.is_ongoing,
          summary: v.summary.trim(),
          skills: v.skills
            .split(",")
            .map((s) => s.trim())
            .filter(Boolean),
          visibility: v.visibility,
        });
      }}
    >
      {allowTypeChange && (
        <label>
          <span className="label">유형</span>
          <select className="input" value={v.type} onChange={(e) => set("type", e.target.value as ItemType)}>
            {ITEM_TYPE_ORDER.map((t) => (
              <option key={t} value={t}>
                {ITEM_TYPE_LABELS[t]}
              </option>
            ))}
          </select>
        </label>
      )}
      <label className={allowTypeChange ? "" : "sm:col-span-2"}>
        <span className="label">제목</span>
        <input className="input" required maxLength={200} value={v.title} onChange={(e) => set("title", e.target.value)} />
      </label>
      <label className="sm:col-span-2">
        <span className="label">영문 제목(영문 Resume에 쓴다)</span>
        <input className="input" maxLength={200} value={v.title_en} onChange={(e) => set("title_en", e.target.value)} />
      </label>
      <label>
        <span className="label">기관</span>
        <input className="input" value={v.organization} onChange={(e) => set("organization", e.target.value)} />
      </label>
      <label>
        <span className="label">역할</span>
        <input className="input" value={v.role} onChange={(e) => set("role", e.target.value)} />
      </label>
      <label>
        <span className="label">시작일</span>
        <input type="date" className="input" value={v.start_date} onChange={(e) => set("start_date", e.target.value)} />
      </label>
      <label>
        <span className="label">종료일</span>
        <input
          type="date"
          className="input"
          value={v.end_date}
          disabled={v.is_ongoing}
          onChange={(e) => set("end_date", e.target.value)}
        />
      </label>
      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" checked={v.is_ongoing} onChange={(e) => set("is_ongoing", e.target.checked)} />
        진행 중이다
      </label>
      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={v.visibility === "public"}
          onChange={(e) => set("visibility", e.target.checked ? "public" : "private")}
        />
        공개 프로필에 보인다
      </label>
      <label className="sm:col-span-2">
        <span className="label">요약</span>
        <textarea className="input min-h-24" value={v.summary} onChange={(e) => set("summary", e.target.value)} />
      </label>
      <label className="sm:col-span-2">
        <span className="label">기술(쉼표로 나눈다)</span>
        <input className="input" value={v.skills} onChange={(e) => set("skills", e.target.value)} placeholder="Python, FastAPI" />
      </label>
      <div className="sm:col-span-2">
        <button className="btn btn-primary" disabled={busy || !v.title.trim()}>
          {submitLabel}
        </button>
      </div>
    </form>
  );
}
