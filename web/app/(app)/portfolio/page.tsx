"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowRight,
  Globe,
  LayoutGrid,
  List,
  NotebookPen,
  Paperclip,
  Plus,
  Quote,
  Search,
  Trees,
  X,
} from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { ErrorText } from "@/components/ErrorText";
import { useGrowth } from "@/components/AppShell";
import { ItemForm } from "@/components/ItemForm";
import { OliveTree } from "@/components/OliveTree";
import { SkillTree } from "@/components/SkillTree";
import { SpecRadar } from "@/components/SpecRadar";
import { EmptyState, PageHeader, Tabs, TypeIcon } from "@/components/ui";
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
  const [view, setView] = useState<"tree" | "list">("tree");
  const [picked, setPicked] = useState<string | null>(null);
  const growth = useGrowth();

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
    if (q && !(i.skills ?? []).some((s) => s.toLowerCase().includes(q)) && !i.title.toLowerCase().includes(q))
      return false;
    if (year) {
      const from = i.start_date?.slice(0, 4) ?? i.end_date?.slice(0, 4);
      const to = i.is_ongoing ? "9999" : (i.end_date?.slice(0, 4) ?? from);
      if (!from || !to || year < from || year > to) return false;
    }
    return true;
  });
  const pickedItem = all.find((i) => i.id === picked) ?? null;
  const skillCount = new Map<string, number>();
  all.forEach((i) => (i.skills ?? []).forEach((sk) => skillCount.set(sk, (skillCount.get(sk) ?? 0) + 1)));
  const topSkills = [...skillCount.entries()].sort((a, b) => b[1] - a[1]).slice(0, 24);
  const groups = ITEM_TYPE_ORDER.map((t) => ({
    type: t,
    items: filtered.filter((i) => i.type === t),
  })).filter((g) => g.items.length > 0);

  return (
    <div className="emerge">
      <PageHeader
        eyebrow="Collection"
        title="모아보기"
        description={`모은 항목 ${all.length}개. 가지는 항목 유형, 잎 하나가 항목 하나다. 공개로 표시한 항목만 공개 프로필에 보인다.`}
        actions={
          <>
            <Tabs
              value={view}
              onChange={setView}
              tabs={[
                {
                  key: "tree",
                  label: (
                    <span className="inline-flex items-center gap-1.5">
                      <Trees size={14} /> 나무
                    </span>
                  ),
                },
                {
                  key: "list",
                  label: (
                    <span className="inline-flex items-center gap-1.5">
                      <List size={14} /> 목록
                    </span>
                  ),
                },
              ]}
            />
            <button className="btn btn-primary" onClick={() => setAdding((v) => !v)}>
              {adding ? <X size={16} /> : <Plus size={16} />} {adding ? "닫기" : "직접 추가"}
            </button>
          </>
        }
      />

      {adding && (
        <div className="card mb-6">
          <p className="mb-4 font-semibold">항목 직접 추가</p>
          <ItemForm submitLabel="추가" busy={create.isPending} onSubmit={(v) => create.mutate(v)} />
          <ErrorText error={create.error} />
        </div>
      )}

      {view === "tree" && all.length > 0 && (
        <div className="mb-8 grid gap-6 xl:grid-cols-[1fr_320px]">
          <section
            className="overflow-hidden rounded-3xl border border-line/80 bg-gradient-to-b from-mint/50 via-paper to-cream/60 p-2 shadow-card sm:p-4"
            data-tour="tree"
          >
            <SkillTree items={all} selected={picked} onSelect={setPicked} />
            <p className="pb-2 text-center text-xs text-muted">
              잎을 누르면 항목을 본다. 점이 붙은 잎은 공개 항목이다.
            </p>
          </section>
          <aside className="space-y-4">
            {pickedItem ? (
              <div className="card">
                <div className="flex items-start gap-3">
                  <TypeIcon type={pickedItem.type} />
                  <div className="min-w-0 flex-1">
                    <p className="font-semibold">{pickedItem.title}</p>
                    <p className="mt-0.5 text-xs text-muted">
                      {[
                        pickedItem.organization,
                        formatPeriod(pickedItem.start_date, pickedItem.end_date, pickedItem.is_ongoing),
                      ]
                        .filter(Boolean)
                        .join(" · ")}
                    </p>
                  </div>
                  <button className="btn-ghost rounded p-1" aria-label="닫기" onClick={() => setPicked(null)}>
                    <X size={14} />
                  </button>
                </div>
                {pickedItem.summary && <p className="mt-3 text-sm text-muted">{pickedItem.summary}</p>}
                {!!pickedItem.skills?.length && (
                  <div className="mt-3 flex flex-wrap gap-1">
                    {pickedItem.skills.map((sk) => (
                      <span key={sk} className="chip">
                        {sk}
                      </span>
                    ))}
                  </div>
                )}
                <Link href={`/portfolio/${pickedItem.id}`} className="btn btn-primary btn-sm mt-4 w-full">
                  자세히 보기 <ArrowRight size={14} />
                </Link>
              </div>
            ) : (
              <div className="card">
                <p className="mb-1 font-semibold">스펙 레이더</p>
                <p className="mb-3 text-xs text-muted">학력을 뺀 7개 축의 항목 수를 목표 기준선과 견준다.</p>
                {growth.data && <SpecRadar growth={growth.data} />}
              </div>
            )}
            {topSkills.length > 0 && (
              <div className="card">
                <p className="mb-3 font-semibold">자주 쓴 기술</p>
                <div className="flex flex-wrap gap-1.5">
                  {topSkills.map(([sk, n]) => (
                    <button
                      key={sk}
                      className="chip hover:bg-accent/40"
                      style={{ fontSize: `${Math.min(15, 11 + n)}px` }}
                      onClick={() => {
                        setSkill(sk);
                        setView("list");
                      }}
                    >
                      {sk} <span className="text-deep/50">{n}</span>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </aside>
        </div>
      )}

      {view === "list" && (
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
              <input
                className="input w-56 pl-9"
                placeholder="제목·기술 검색"
                value={skill}
                onChange={(e) => setSkill(e.target.value)}
              />
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
      )}

      <ErrorText error={items.error} />
      {items.isSuccess && all.length === 0 && (
        <EmptyState
          icon={LayoutGrid}
          illustration={<OliveTree level={0} className="mb-2 h-36" />}
          title="아직 화분에 싹이 없다"
          description="일기를 쓰면 AI가 경험 후보를 찾아 준다. 그중 '추가'한 경험이 이 나무의 가지와 잎이 된다. 이미 쓴 이력서나 GitHub가 있다면 한 번에 가져올 수도 있다."
          action={
            <>
              <Link href="/journal" className="btn btn-primary">
                <NotebookPen size={15} /> 첫 일기 쓰기
              </Link>
              <Link href="/onboarding?step=3" className="btn">
                이력서·GitHub 가져오기
              </Link>
            </>
          }
        />
      )}
      {items.isSuccess && all.length > 0 && groups.length === 0 && (
        <p className="text-sm text-muted">조건에 맞는 항목이 없다.</p>
      )}
      {view === "list" && (
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
                          {[i.organization, formatPeriod(i.start_date, i.end_date, i.is_ongoing)]
                            .filter(Boolean)
                            .join(" · ")}
                        </p>
                      </div>
                      {i.visibility === "public" && (
                        <Globe size={15} className="shrink-0 text-accent-2" aria-label="공개" />
                      )}
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
      )}
    </div>
  );
}
