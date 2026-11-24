"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, RefreshCw, Sparkles, X } from "lucide-react";
import { useEffect, useState } from "react";
import { ErrorText } from "@/components/ErrorText";
import { Spinner } from "@/components/ui";
import { api, post } from "@/lib/api";
import type { Job, Metric, Proposal } from "@/lib/types";

type SummaryPatch = { summary_replace?: string; role?: string; metrics_add?: Metric[]; skills_add?: string[] };

/** 항목 상세의 '근거로 요약 다시 쓰기'와, 만들어진 요약 제안(반영·버리기). */
export function SummaryProposal({ itemId, hasSources }: { itemId: string; hasSources: boolean }) {
  const qc = useQueryClient();
  const [jobId, setJobId] = useState<string | null>(null);
  const proposals = useQuery({
    queryKey: ["proposals"],
    queryFn: () => api<{ proposals: Proposal[] }>("/proposals?status=pending"),
  });
  const job = useQuery({
    queryKey: ["job", jobId],
    queryFn: () => api<Job>(`/jobs/${jobId}`),
    enabled: !!jobId,
    refetchInterval: (q) => {
      const s = q.state.data?.status;
      return s === "succeeded" || s === "failed" ? false : 1500;
    },
  });
  const jobStatus = job.data?.status;
  useEffect(() => {
    if (jobStatus === "succeeded" || jobStatus === "failed") qc.invalidateQueries({ queryKey: ["proposals"] });
  }, [jobStatus, qc]);
  const refresh = () =>
    ["proposals", "item", "items", "pending-count", "notifications"].forEach((k) =>
      qc.invalidateQueries({ queryKey: [k] }),
    );
  const start = useMutation({
    mutationFn: () => post<{ job_id: string }>(`/items/${itemId}/summarize`),
    onSuccess: (r) => setJobId(r.job_id),
  });
  const accept = useMutation({ mutationFn: (id: string) => post(`/proposals/${id}/accept`), onSuccess: refresh });
  const reject = useMutation({ mutationFn: (id: string) => post(`/proposals/${id}/reject`), onSuccess: refresh });

  const p = proposals.data?.proposals.find(
    (x) => x.item_id === itemId && x.kind === "update_item" && x.payload.source === "activity_summary",
  );
  const running = !!jobId && !["succeeded", "failed"].includes(job.data?.status ?? "");
  const patch = (p?.payload.patch ?? {}) as SummaryPatch;

  if (p && patch.summary_replace) {
    return (
      <div className="rounded-xl border border-accent/50 bg-mint/60 p-4">
        <p className="mb-2 flex items-center gap-2 text-sm font-semibold text-deep">
          <Sparkles size={15} /> 근거를 모아 새로 쓴 요약이다
        </p>
        <p className="text-[15px] leading-relaxed">{patch.summary_replace}</p>
        {(patch.role || !!patch.metrics_add?.length || !!patch.skills_add?.length) && (
          <p className="mt-2 text-xs text-muted">
            {[
              patch.role && `역할: ${patch.role}`,
              patch.metrics_add?.length && `수치: ${patch.metrics_add.map((m) => `${m.name} ${m.value}`).join(", ")}`,
              patch.skills_add?.length && `기술: ${patch.skills_add.join(", ")}`,
            ]
              .filter(Boolean)
              .join(" · ")}
          </p>
        )}
        <div className="mt-3 flex gap-2">
          <button className="btn btn-primary btn-sm" disabled={accept.isPending} onClick={() => accept.mutate(p.id)}>
            <Check size={14} /> 이 요약으로 바꾸기
          </button>
          <button className="btn btn-sm" disabled={reject.isPending} onClick={() => reject.mutate(p.id)}>
            <X size={14} /> 지금 요약 유지
          </button>
        </div>
        <ErrorText error={accept.error ?? reject.error} />
      </div>
    );
  }
  if (!hasSources) return null;
  return (
    <div className="flex flex-wrap items-center gap-3 border-t border-line/70 pt-3">
      {running ? (
        <Spinner label="쌓인 기록을 모아 요약을 쓰고 있다." />
      ) : (
        <>
          <button className="btn btn-sm" onClick={() => start.mutate()} disabled={start.isPending}>
            <RefreshCw size={14} /> 근거로 요약 다시 쓰기
          </button>
          <span className="text-xs text-muted">연결된 일기 문장만으로 요약을 새로 쓰고, 바꾸기 전에 보여 준다.</span>
        </>
      )}
      {job.data?.status === "succeeded" && !p && (
        <p className="w-full text-xs text-muted">새로 쓸 만한 내용이 없었다. 기록이 더 쌓이면 다시 해 본다.</p>
      )}
      {job.data?.status === "failed" && (
        <p className="w-full text-xs text-red-700">요약을 만들지 못했다. 잠시 뒤 다시 해 본다.</p>
      )}
      <ErrorText error={start.error} />
    </div>
  );
}
