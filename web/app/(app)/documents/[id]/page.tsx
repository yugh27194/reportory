"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, ArrowLeft, Copy, Download, Globe, Lock, RefreshCw, Trash2 } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { DocFormatIcon } from "@/components/DocFormatIcon";
import { ErrorText } from "@/components/ErrorText";
import { Spinner, StatusDot } from "@/components/ui";
import { api, del, patch, post } from "@/lib/api";
import { DOC_FORMATS, type DocContent, type DocVersion, type DocumentRow } from "@/lib/types";

type DocDetail = DocumentRow & { versions: DocVersion[] };

function sectionText(content: DocContent, key: string): string {
  const x = content["x-reportory"];
  const sec = x.sections.find((s) => s.key === key);
  if (!sec) return "";
  return sec.items
    .map((id) => {
      const i = x.items[id];
      const period = [i.period[0]?.slice(0, 7), i.is_ongoing ? "현재" : i.period[1]?.slice(0, 7)].filter(Boolean).join(" ~ ");
      const head = [i.title, i.organization, i.role, period].filter(Boolean).join(" | ");
      return [head, ...i.lines.map((l) => `- ${l}`)].join("\n");
    })
    .join("\n\n");
}

function CopySections({ content }: { content: DocContent }) {
  const [copied, setCopied] = useState<string | null>(null);
  const sections = content["x-reportory"].sections.filter((s) => s.items.length);
  return (
    <div className="card">
      <h3 className="section-title mb-1">섹션별 복사</h3>
      <p className="mb-3 text-xs text-muted">회사 자체 양식에 옮겨 적을 때 쓴다.</p>
      <div className="flex flex-wrap gap-2">
        {sections.map((s) => (
          <button
            key={s.key}
            className="btn btn-sm"
            onClick={async () => {
              await navigator.clipboard.writeText(sectionText(content, s.key));
              setCopied(s.key);
              setTimeout(() => setCopied(null), 1500);
            }}
          >
            <Copy size={12} /> {copied === s.key ? "복사했다" : s.label}
          </button>
        ))}
      </div>
    </div>
  );
}

export default function DocumentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const qc = useQueryClient();
  const doc = useQuery({
    queryKey: ["document", id],
    queryFn: () => api<DocDetail>(`/documents/${id}`),
    refetchInterval: (q) =>
      q.state.data?.versions.some((v) => v.status === "queued" || v.status === "running") ? 2500 : false,
  });
  const [picked, setPicked] = useState<number | null>(null);
  const versions = doc.data?.versions ?? [];
  const current = picked ?? versions[0]?.version ?? null;
  const ver = useQuery({
    queryKey: ["document", id, "version", current],
    queryFn: () => api<DocVersion>(`/documents/${id}/versions/${current}`),
    enabled: current !== null && versions.find((v) => v.version === current)?.status === "succeeded",
  });

  const refresh = () => qc.invalidateQueries({ queryKey: ["document", id] });
  const pdf = useMutation({
    mutationFn: () => api<{ url: string }>(`/documents/${id}/versions/${current}/pdf`),
    onSuccess: (r) => window.open(r.url, "_blank", "noopener"),
  });
  const regenerate = useMutation({
    mutationFn: () =>
      post(`/documents/${id}/versions`, { selected_item_ids: versions[0]?.selected_item_ids ?? [] }),
    onSuccess: () => {
      setPicked(null);
      refresh();
    },
  });
  const togglePublic = useMutation({
    mutationFn: () => patch(`/documents/${id}`, { is_public: !doc.data?.is_public }),
    onSuccess: refresh,
  });
  const remove = useMutation({
    mutationFn: () => del(`/documents/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["documents"] });
      router.push("/documents");
    },
  });

  if (doc.error) return <ErrorText error={doc.error} />;
  const d = doc.data;
  if (!d) return <Spinner label="불러오는 중이다" />;
  const meta = versions.find((v) => v.version === current);
  const label = DOC_FORMATS.find((f) => f.key === d.format)?.label;
  const warnings = ver.data?.options.warnings ?? [];

  return (
    <div className="space-y-6">
      <Link href="/documents" className="inline-flex items-center gap-1 text-sm text-muted hover:text-ink">
        <ArrowLeft size={14} /> 문서
      </Link>
      <header className="flex flex-wrap items-start gap-4">
        <DocFormatIcon format={d.format} />
        <div className="mr-auto min-w-0">
          <p className="text-xs font-semibold text-muted">{label}</p>
          <h1 className="text-2xl font-bold tracking-tight">{d.title}</h1>
          {d.target_description && <p className="mt-1 line-clamp-2 max-w-2xl text-sm text-muted">{d.target_description}</p>}
        </div>
        <div className="flex flex-wrap gap-2">
          <button className="btn btn-primary" disabled={!meta?.has_pdf || pdf.isPending} onClick={() => pdf.mutate()}>
            <Download size={16} /> PDF
          </button>
          <button className="btn" onClick={() => regenerate.mutate()} disabled={regenerate.isPending || !versions.length}>
            <RefreshCw size={14} /> 다시 만들기
          </button>
          <button className="btn" onClick={() => togglePublic.mutate()}>
            {d.is_public ? <Globe size={14} className="text-accent-2" /> : <Lock size={14} />}
            {d.is_public ? "프로필에 공개 중" : "비공개"}
          </button>
          <button className="btn btn-ghost btn-danger" onClick={() => confirm("문서와 모든 버전을 지운다.") && remove.mutate()}>
            <Trash2 size={14} />
          </button>
        </div>
      </header>
      <ErrorText error={pdf.error ?? regenerate.error ?? togglePublic.error ?? remove.error} />

      <div className="grid gap-6 lg:grid-cols-[220px_1fr]">
        <aside className="space-y-4">
          <div className="card p-3">
            <p className="section-title px-2 pb-2">버전</p>
            <ul className="space-y-1">
              {versions.map((v) => (
                <li key={v.id}>
                  <button
                    onClick={() => setPicked(v.version)}
                    className={`flex w-full items-center gap-2 rounded-lg px-2 py-2 text-left text-sm ${
                      v.version === current ? "bg-mint text-deep" : "hover:bg-cream"
                    }`}
                  >
                    <span className="font-semibold">v{v.version}</span>
                    <span className="text-xs text-muted">{new Date(v.created_at).toLocaleDateString("ko-KR")}</span>
                    <span className="ml-auto">
                      <StatusDot status={v.status} />
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
          {ver.data?.content && d.format === "resume_ko" && <CopySections content={ver.data.content} />}
        </aside>
        <section className="space-y-4">
          {warnings.length > 0 && (
            <div className="rounded-2xl bg-amber-50 p-4 text-sm text-amber-900">
              <p className="mb-1 flex items-center gap-2 font-semibold">
                <AlertTriangle size={16} /> 확인할 점
              </p>
              <ul className="ml-6 list-disc space-y-0.5">
                {warnings.map((w) => (
                  <li key={w}>{w}</li>
                ))}
              </ul>
            </div>
          )}
          {meta && (meta.status === "queued" || meta.status === "running") && (
            <div className="card flex h-64 items-center justify-center">
              <Spinner label="문장을 다듬고 PDF를 만드는 중이다." />
            </div>
          )}
          {meta?.status === "failed" && <p className="text-sm text-red-700">이 버전을 만들지 못했다. 다시 만들기를 눌러 보세요.</p>}
          {ver.data?.html && (
            <div className="overflow-hidden rounded-2xl bg-ink/5 p-3 ring-1 ring-line sm:p-6">
              <iframe
                title="문서 미리보기"
                srcDoc={ver.data.html}
                sandbox=""
                className="mx-auto block h-[1123px] w-full max-w-[794px] rounded bg-white shadow-lift"
              />
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
