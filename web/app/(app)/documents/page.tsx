"use client";

import { useQuery } from "@tanstack/react-query";
import { FileText, Globe, Plus } from "lucide-react";
import Link from "next/link";
import { DocFormatIcon } from "@/components/DocFormatIcon";
import { ErrorText } from "@/components/ErrorText";
import { EmptyState, PageHeader, StatusDot } from "@/components/ui";
import { api } from "@/lib/api";
import { DOC_FORMATS, type DocumentRow } from "@/lib/types";

export default function DocumentsPage() {
  const docs = useQuery({
    queryKey: ["documents"],
    queryFn: () => api<{ documents: DocumentRow[] }>("/documents"),
  });
  const label = (f: string) => DOC_FORMATS.find((x) => x.key === f)?.label ?? f;

  return (
    <div>
      <PageHeader
        eyebrow="Documents"
        title="문서"
        description="승인한 항목으로 지원 목적에 맞는 문서를 만든다. 문장마다 근거가 있는 내용만 들어간다."
        actions={
          <Link href="/documents/new" className="btn btn-primary">
            <Plus size={16} /> 새 문서
          </Link>
        }
      />
      <ErrorText error={docs.error} />
      {docs.isSuccess && docs.data.documents.length === 0 && (
        <div className="space-y-6">
          <EmptyState icon={FileText} title="아직 만든 문서가 없다" description="형식을 고르고 지원 대상을 적으면 알맞은 항목을 골라 준다." />
          <div className="grid gap-3 sm:grid-cols-2">
            {DOC_FORMATS.map((f) => (
              <Link key={f.key} href={`/documents/new?format=${f.key}`} className="card card-hover flex gap-4">
                <DocFormatIcon format={f.key} />
                <div>
                  <p className="font-semibold">{f.label}</p>
                  <p className="mt-0.5 text-sm text-muted">{f.desc}</p>
                </div>
              </Link>
            ))}
          </div>
        </div>
      )}
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {docs.data?.documents.map((d) => (
          <Link key={d.id} href={`/documents/${d.id}`} className="card card-hover flex flex-col gap-3">
            <div className="flex items-start gap-3">
              <DocFormatIcon format={d.format} />
              <div className="min-w-0 flex-1">
                <p className="truncate font-semibold">{d.title}</p>
                <p className="text-xs text-muted">{label(d.format)}</p>
              </div>
              {d.is_public && <Globe size={15} className="text-accent-2" aria-label="공개" />}
            </div>
            {d.target_description && <p className="line-clamp-2 text-sm text-muted">{d.target_description}</p>}
            <div className="mt-auto flex items-center gap-3 text-xs text-muted">
              {d.latest ? (
                <>
                  <span>버전 {d.latest.version}</span>
                  <StatusDot status={d.latest.status} />
                </>
              ) : (
                <span>아직 만든 버전이 없다</span>
              )}
              <span className="ml-auto">{new Date(d.updated_at).toLocaleDateString("ko-KR")}</span>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
