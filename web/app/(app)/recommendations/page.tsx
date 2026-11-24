"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CalendarClock,
  Compass,
  EyeOff,
  Heart,
  Link2,
  RefreshCw,
  Send,
  Sparkles,
  SquareArrowOutUpRight,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { ErrorText } from "@/components/ErrorText";
import { EmptyState, PageHeader, Spinner, TypeIcon } from "@/components/ui";
import { api, post } from "@/lib/api";
import { daysLeft, ddayLabel } from "@/lib/dday";
import { CATEGORY_LABELS, type Job, type OpportunityCategory, type Recommendation } from "@/lib/types";

function DdayBadge({ date }: { date: string | null }) {
  const d = daysLeft(date);
  const urgent = d !== null && d <= 7;
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-bold ${
        urgent ? "bg-ink text-accent" : "bg-cream text-ink/80"
      }`}
    >
      <CalendarClock size={12} /> {ddayLabel(date)}
    </span>
  );
}

function RecoCard({ r }: { r: Recommendation }) {
  const qc = useQueryClient();
  const fb = useMutation({
    mutationFn: (feedback: "interested" | "dismissed" | "applied") =>
      post(`/recommendations/${r.id}/feedback`, { feedback }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["recommendations"] });
      qc.invalidateQueries({ queryKey: ["applications"] });
    },
  });
  const interested = r.feedback === "interested";
  return (
    <article className={`card flex flex-col gap-3 ${interested ? "border-accent/60" : ""}`}>
      <div className="flex flex-wrap items-center gap-2">
        <span className="chip chip-ink">{CATEGORY_LABELS[r.category]}</span>
        <DdayBadge date={r.apply_deadline} />
        {r.added_by_me && <span className="chip chip-cream">내가 추가</span>}
        {r.score_breakdown.gap > 0 && <span className="chip">빈 경험 채우기</span>}
      </div>
      <div>
        <h3 className="text-lg leading-snug font-bold">{r.title}</h3>
        <p className="mt-0.5 text-xs text-muted">
          {[r.organizer, r.source_site, r.apply_deadline && `마감 ${r.apply_deadline}`].filter(Boolean).join(" · ")}
        </p>
      </div>
      {r.summary && <p className="line-clamp-3 text-sm text-ink/80">{r.summary}</p>}
      {r.reason && (
        <div className="rounded-xl bg-mint/70 p-3 text-sm">
          <p className="flex gap-2 text-deep">
            <Sparkles size={15} className="mt-0.5 shrink-0" />
            <span>{r.reason}</span>
          </p>
          {r.reason_items.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1.5 pl-6">
              {r.reason_items.map((i) => (
                <Link
                  key={i.id}
                  href={`/portfolio/${i.id}`}
                  className="inline-flex items-center gap-1.5 rounded-full bg-white px-2 py-0.5 text-xs hover:text-deep"
                >
                  <TypeIcon type={i.type} size="sm" /> {i.title}
                </Link>
              ))}
            </div>
          )}
        </div>
      )}
      {r.tags.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {r.tags.map((t) => (
            <span key={t} className="chip chip-cream">
              {t}
            </span>
          ))}
        </div>
      )}
      <div className="mt-auto flex flex-wrap items-center gap-2 border-t border-line/70 pt-3">
        <a
          href={r.source_url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 text-sm text-deep hover:underline"
        >
          원문 보기 <SquareArrowOutUpRight size={13} />
        </a>
        <span className="ml-auto flex gap-1.5">
          {!interested && (
            <button
              className="btn btn-ghost btn-sm"
              disabled={fb.isPending}
              onClick={() => fb.mutate("dismissed")}
              title="다시 추천하지 않는다"
            >
              <EyeOff size={14} /> 숨김
            </button>
          )}
          {interested ? (
            <Link href="/applications" className="btn btn-sm">
              <Heart size={14} className="fill-accent text-accent" /> 관심 목록에 있다
            </Link>
          ) : (
            <button className="btn btn-sm" disabled={fb.isPending} onClick={() => fb.mutate("interested")}>
              <Heart size={14} /> 관심
            </button>
          )}
          <button className="btn btn-primary btn-sm" disabled={fb.isPending} onClick={() => fb.mutate("applied")}>
            <Send size={14} /> 지원함
          </button>
        </span>
      </div>
      <ErrorText error={fb.error} />
    </article>
  );
}

function AddByUrl() {
  const qc = useQueryClient();
  const [url, setUrl] = useState("");
  const [jobId, setJobId] = useState<string | null>(null);
  const add = useMutation({
    mutationFn: () => post<{ job_id: string }>("/opportunities/from-url", { url: url.trim() }),
    onSuccess: (r) => {
      setJobId(r.job_id);
      setUrl("");
    },
  });
  const job = useQuery({
    queryKey: ["job", jobId],
    queryFn: () => api<Job>(`/jobs/${jobId}`),
    enabled: !!jobId,
    refetchInterval: (q) => {
      const s = q.state.data?.status;
      if (s === "succeeded" || s === "failed") return false;
      return 2000;
    },
  });
  const status = job.data?.status;
  useEffect(() => {
    // 공고를 더하면 추천 계산이 이어서 돈다. 목록을 다시 읽으면 계산이 끝날 때까지 알아서 새로 고친다.
    if (status === "succeeded") qc.invalidateQueries({ queryKey: ["recommendations"] });
  }, [status, qc]);
  return (
    <div className="card">
      <p className="mb-1 flex items-center gap-2 font-semibold">
        <Link2 size={16} className="text-deep" /> 찾은 공고를 직접 넣기
      </p>
      <p className="mb-3 text-sm text-muted">
        공고 상세 페이지 주소를 넣으면 내용을 읽어 나에게만 보이는 추천으로 더한다.
      </p>
      <form
        className="flex flex-wrap gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          if (url.trim()) add.mutate();
        }}
      >
        <input
          className="input min-w-0 flex-1"
          placeholder="https://..."
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          inputMode="url"
        />
        <button className="btn btn-primary" disabled={!url.trim() || add.isPending}>
          공고 추가
        </button>
      </form>
      <ErrorText error={add.error} />
      {jobId && (status === "queued" || status === "running" || !status) && (
        <div className="mt-3">
          <Spinner label="페이지를 읽고 공고를 정리하고 있다." />
        </div>
      )}
      {status === "succeeded" && (
        <p className="mt-3 text-sm text-deep">
          &lsquo;{String(job.data?.result?.title ?? "공고")}&rsquo;를 더했다. 추천 목록에 곧 나타난다.
        </p>
      )}
      {status === "failed" && (
        <p className="mt-3 text-sm text-red-700">
          {(job.data?.last_error ?? "").replace(/^\w+: /, "") || "공고를 읽지 못했다."}
        </p>
      )}
    </div>
  );
}

export default function RecommendationsPage() {
  const qc = useQueryClient();
  const [cat, setCat] = useState<OpportunityCategory | "">("");
  const recs = useQuery({
    queryKey: ["recommendations"],
    queryFn: () => api<{ recommendations: Recommendation[]; last_job: { status: string } | null }>("/recommendations"),
    refetchInterval: (q) => (["queued", "running"].includes(q.state.data?.last_job?.status ?? "") ? 3000 : false),
  });
  const refresh = useMutation({
    mutationFn: () => post("/recommendations/refresh"),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["recommendations"] }),
  });
  const all = recs.data?.recommendations ?? [];
  const cats = [...new Set(all.map((r) => r.category))];
  const shown = all.filter((r) => !cat || r.category === cat);
  const busy = ["queued", "running"].includes(recs.data?.last_job?.status ?? "");

  return (
    <div>
      <PageHeader
        eyebrow="Discover"
        title="활동 추천"
        description="매일 새벽 모집 공고를 모아, 내 목표와 모은 경험에 맞춰 고른다. 마감이 지났거나 지원 자격이 맞지 않는 공고는 빠진다."
        actions={
          <button className="btn" disabled={busy || refresh.isPending} onClick={() => refresh.mutate()}>
            <RefreshCw size={15} className={busy ? "animate-spin" : ""} />{" "}
            {busy ? "다시 고르는 중이다" : "추천 다시 고르기"}
          </button>
        }
      />
      <ErrorText error={refresh.error ?? recs.error} />
      <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
        <section>
          {cats.length > 1 && (
            <div className="mb-4 flex flex-wrap gap-2">
              <button
                onClick={() => setCat("")}
                className={`rounded-full px-3.5 py-1.5 text-sm ${cat === "" ? "bg-ink text-white" : "bg-white text-muted ring-1 ring-line hover:text-ink"}`}
              >
                전체 {all.length}
              </button>
              {cats.map((c) => (
                <button
                  key={c}
                  onClick={() => setCat(cat === c ? "" : c)}
                  className={`rounded-full px-3.5 py-1.5 text-sm ${cat === c ? "bg-ink text-white" : "bg-white text-muted ring-1 ring-line hover:text-ink"}`}
                >
                  {CATEGORY_LABELS[c]} {all.filter((r) => r.category === c).length}
                </button>
              ))}
            </div>
          )}
          {recs.isSuccess && all.length === 0 && (
            <EmptyState
              icon={Compass}
              title="아직 추천할 공고가 없다"
              description="공고는 매일 새벽에 모이고, 내 관심 분야와 모은 경험에 맞춰 추천을 고른다. 관심 분야를 적어 두면 첫 추천이 더 잘 맞는다. 눈여겨본 공고가 있다면 오른쪽에 주소를 바로 넣어 보세요."
              action={
                <>
                  <Link href="/settings" className="btn btn-primary">
                    관심 분야 적기
                  </Link>
                  <button className="btn" disabled={busy || refresh.isPending} onClick={() => refresh.mutate()}>
                    <RefreshCw size={14} /> 추천 다시 고르기
                  </button>
                </>
              }
            />
          )}
          <div className="grid gap-4 xl:grid-cols-2">
            {shown.map((r) => (
              <RecoCard key={r.id} r={r} />
            ))}
          </div>
        </section>
        <aside className="space-y-4">
          <AddByUrl />
          <div className="rounded-2xl bg-cream p-4 text-sm text-muted">
            <p className="mb-2 font-semibold text-deep">이렇게 고른다</p>
            <ul className="space-y-1">
              <li>· 내가 모은 경험·관심 분야와 비슷한 공고를 먼저 둔다.</li>
              <li>· 목표에 아직 없는 경험(인턴, 연구 등)을 채우는 공고에 점수를 더한다.</li>
              <li>· 관심·숨김을 누를수록 취향을 배운다.</li>
              <li>· 마감이 2주 안이면 조금 앞에 둔다.</li>
            </ul>
          </div>
        </aside>
      </div>
    </div>
  );
}
