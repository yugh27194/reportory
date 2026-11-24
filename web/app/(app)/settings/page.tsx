"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Compass, Download, ExternalLink, Plus, ShieldCheck, Trash2, Upload, X } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ErrorText } from "@/components/ErrorText";
import { useTour } from "@/components/Tour";
import { PageHeader, Spinner } from "@/components/ui";
import { api, del, patch, post } from "@/lib/api";
import { env } from "@/lib/env";
import { supabaseBrowser } from "@/lib/supabase/client";
import type { Profile } from "@/lib/types";

const GOALS = { grad_school: "대학원 진학", employment: "취업", undecided: "아직 정하지 않았다" } as const;
const list = (s: string) =>
  s
    .split(",")
    .map((x) => x.trim())
    .filter(Boolean);

function Section({ title, desc, children }: { title: string; desc?: string; children: React.ReactNode }) {
  return (
    <section className="card grid gap-6 md:grid-cols-[220px_1fr]">
      <div>
        <h2 className="font-semibold">{title}</h2>
        {desc && <p className="mt-1 text-sm text-muted">{desc}</p>}
      </div>
      <div className="min-w-0">{children}</div>
    </section>
  );
}

type Link_ = { label: string; url: string };

export default function SettingsPage() {
  const qc = useQueryClient();
  const router = useRouter();
  const tour = useTour();
  const me = useQuery({ queryKey: ["me"], queryFn: () => api<{ profile: Profile }>("/me") });
  const [form, setForm] = useState({
    display_name: "",
    display_name_en: "",
    headline: "",
    handle: "",
    goal: "undecided" as Profile["goal"],
    interests: "",
    target_roles: "",
    school: "",
    major: "",
    grade: "",
    email_public: "",
  });
  const [links, setLinks] = useState<Link_[]>([]);
  const [saved, setSaved] = useState(false);
  const [confirmText, setConfirmText] = useState("");

  useEffect(() => {
    const p = me.data?.profile;
    if (!p) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setForm({
      display_name: p.display_name ?? "",
      display_name_en: p.display_name_en ?? "",
      headline: p.headline ?? "",
      handle: p.handle ?? "",
      goal: p.goal,
      interests: p.interests.join(", "),
      target_roles: p.target_roles.join(", "),
      school: p.school ?? "",
      major: p.major ?? "",
      grade: p.grade ? String(p.grade) : "",
      email_public: p.email_public ?? "",
    });
    setLinks(p.links ?? []);
  }, [me.data]);

  const done = () => {
    setSaved(true);
    qc.invalidateQueries({ queryKey: ["me"] });
  };
  const save = useMutation({
    mutationFn: () =>
      patch("/me/profile", {
        display_name: form.display_name || null,
        display_name_en: form.display_name_en || null,
        headline: form.headline || null,
        handle: form.handle || null,
        goal: form.goal,
        interests: list(form.interests),
        target_roles: list(form.target_roles),
        school: form.school || null,
        major: form.major || null,
        grade: form.grade ? Number(form.grade) : null,
        email_public: form.email_public || null,
        links: links.filter((l) => l.label.trim() && l.url.trim()),
      }),
    onSuccess: done,
  });
  const togglePublic = useMutation({
    mutationFn: (on: boolean) => patch("/me/profile", { public_profile_enabled: on }),
    onSuccess: done,
  });
  const consent = useMutation({ mutationFn: () => post("/me/consent"), onSuccess: done });

  const latestExport = useQuery({
    queryKey: ["export-latest"],
    queryFn: () => api<{ job: { id: string; status: string; updated_at: string } | null }>("/export/latest"),
    refetchInterval: (q) => (["queued", "running"].includes(q.state.data?.job?.status ?? "") ? 2500 : false),
  });
  const startExport = useMutation({
    mutationFn: () => post("/export"),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["export-latest"] }),
  });
  const download = useMutation({
    mutationFn: (jobId: string) => api<{ url: string }>(`/export/${jobId}/url`),
    onSuccess: (r) => window.open(r.url, "_blank", "noopener"),
  });
  const deleteAccount = useMutation({
    mutationFn: () => del("/account", { confirm: confirmText }),
    onSuccess: async () => {
      await supabaseBrowser().auth.signOut();
      router.replace("/");
    },
  });

  const p = me.data?.profile;
  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    setSaved(false);
    setForm((f) => ({ ...f, [k]: e.target.value }));
  };
  const exp = latestExport.data?.job;

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Settings"
        title="설정"
        actions={
          <button className="btn" onClick={() => tour.start()}>
            <Compass size={15} /> 사용법 다시 보기
          </button>
        }
      />

      <Section title="프로필" desc="문서 머리말과 공개 프로필에 쓰인다.">
        <form
          className="grid gap-4 sm:grid-cols-2"
          onSubmit={(e) => {
            e.preventDefault();
            save.mutate();
          }}
        >
          <label>
            <span className="label">이름</span>
            <input className="input" value={form.display_name} onChange={set("display_name")} />
          </label>
          <label>
            <span className="label">영문 이름</span>
            <input className="input" value={form.display_name_en} onChange={set("display_name_en")} />
          </label>
          <label className="sm:col-span-2">
            <span className="label">한 줄 소개</span>
            <input
              className="input"
              maxLength={120}
              value={form.headline}
              onChange={set("headline")}
              placeholder="예: 데이터로 문제를 푸는 컴퓨터학과 3학년이다."
            />
          </label>
          <label>
            <span className="label">목표</span>
            <select className="input" value={form.goal} onChange={set("goal")}>
              {Object.entries(GOALS).map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span className="label">학년</span>
            <input className="input" inputMode="numeric" value={form.grade} onChange={set("grade")} />
          </label>
          <label>
            <span className="label">학교</span>
            <input className="input" value={form.school} onChange={set("school")} />
          </label>
          <label>
            <span className="label">전공</span>
            <input className="input" value={form.major} onChange={set("major")} />
          </label>
          <label className="sm:col-span-2">
            <span className="label">관심 분야(쉼표로 나눈다)</span>
            <input className="input" value={form.interests} onChange={set("interests")} />
          </label>
          <label className="sm:col-span-2">
            <span className="label">목표 직무(쉼표로 나눈다)</span>
            <input className="input" value={form.target_roles} onChange={set("target_roles")} />
          </label>
          <label>
            <span className="label">공개 이메일</span>
            <input className="input" type="email" value={form.email_public} onChange={set("email_public")} />
          </label>
          <label>
            <span className="label">공개 프로필 주소</span>
            <div className="flex items-center rounded-lg border border-line bg-cream/40 pl-3 text-sm text-muted focus-within:ring-3 focus-within:ring-accent/25">
              /p/
              <input
                className="w-full bg-transparent px-1 py-2 text-ink outline-none"
                value={form.handle}
                onChange={set("handle")}
                placeholder="영문 소문자·숫자 3~30자"
              />
            </div>
          </label>
          <div className="sm:col-span-2">
            <span className="label">링크</span>
            <div className="space-y-2">
              {links.map((l, i) => (
                <div key={i} className="flex gap-2">
                  <input
                    className="input w-32"
                    placeholder="이름"
                    value={l.label}
                    onChange={(e) =>
                      setLinks((ls) => ls.map((x, j) => (j === i ? { ...x, label: e.target.value } : x)))
                    }
                  />
                  <input
                    className="input"
                    placeholder="https://"
                    value={l.url}
                    onChange={(e) => setLinks((ls) => ls.map((x, j) => (j === i ? { ...x, url: e.target.value } : x)))}
                  />
                  <button
                    type="button"
                    className="btn btn-ghost"
                    onClick={() => setLinks((ls) => ls.filter((_, j) => j !== i))}
                    aria-label="링크 지우기"
                  >
                    <X size={14} />
                  </button>
                </div>
              ))}
              <button
                type="button"
                className="btn btn-sm"
                onClick={() => setLinks((ls) => [...ls, { label: "", url: "" }])}
              >
                <Plus size={12} /> 링크 추가
              </button>
            </div>
          </div>
          <div className="flex items-center gap-3 sm:col-span-2">
            <button className="btn btn-primary" disabled={save.isPending}>
              저장
            </button>
            {saved && <span className="text-sm text-deep">저장했다.</span>}
          </div>
          <div className="sm:col-span-2">
            <ErrorText error={save.error} />
          </div>
        </form>
      </Section>

      <Section title="공개 프로필" desc="공개로 표시한 승인 항목과 공개 문서만 보인다.">
        <div className="flex flex-wrap items-center gap-3">
          {p?.public_profile_enabled && p.handle ? (
            <Link
              className="inline-flex items-center gap-1 text-sm font-medium text-deep underline"
              href={`/p/${p.handle}`}
              target="_blank"
            >
              {env.siteUrl.replace(/^https?:\/\//, "")}/p/{p.handle} <ExternalLink size={14} />
            </Link>
          ) : (
            <p className="text-sm text-muted">지금은 꺼져 있다.</p>
          )}
          <button
            className="btn ml-auto"
            disabled={togglePublic.isPending || !p}
            onClick={() => togglePublic.mutate(!p?.public_profile_enabled)}
          >
            {p?.public_profile_enabled ? "공개 끄기" : "공개 켜기"}
          </button>
        </div>
        <ErrorText error={togglePublic.error} />
      </Section>

      <Section title="기록 가져오기" desc="이력서, GitHub, LinkedIn에서 항목을 가져온다.">
        <Link href="/onboarding?step=3" className="btn">
          <Upload size={14} /> 가져오기 화면 열기
        </Link>
      </Section>

      <Section title="LLM 처리 동의" desc="일기·업로드 파일 분석에 외부 LLM API를 쓴다.">
        {p?.llm_consent_at ? (
          <p className="flex items-center gap-2 text-sm text-muted">
            <ShieldCheck size={16} className="text-deep" />
            {new Date(p.llm_consent_at).toLocaleDateString("ko-KR")}에 동의했다.
          </p>
        ) : (
          <button className="btn" onClick={() => consent.mutate()} disabled={consent.isPending}>
            동의하기
          </button>
        )}
      </Section>

      <Section title="데이터 내보내기" desc="JSON Resume, 항목, 일기, 증빙 파일을 ZIP 하나로 받는다.">
        <div className="flex flex-wrap items-center gap-3">
          <button
            className="btn"
            onClick={() => startExport.mutate()}
            disabled={startExport.isPending || ["queued", "running"].includes(exp?.status ?? "")}
          >
            내보내기 파일 만들기
          </button>
          {exp && ["queued", "running"].includes(exp.status) && <Spinner label="준비하는 중이다" />}
          {exp?.status === "succeeded" && (
            <button className="btn btn-primary" onClick={() => download.mutate(exp.id)}>
              <Download size={14} /> {new Date(exp.updated_at).toLocaleString("ko-KR")} 파일 받기
            </button>
          )}
        </div>
        <ErrorText error={startExport.error ?? download.error} />
      </Section>

      <Section title="계정 삭제" desc="모든 기록과 파일을 지운다. 되돌릴 수 없다.">
        <div className="space-y-3">
          <p className="text-sm text-muted">
            먼저 데이터를 내보내 두는 것을 권한다. 삭제하려면 아래에 <b className="text-ink">계정 삭제</b>를 입력한다.
          </p>
          <div className="flex flex-wrap gap-2">
            <input
              className="input w-48"
              value={confirmText}
              onChange={(e) => setConfirmText(e.target.value)}
              placeholder="계정 삭제"
            />
            <button
              className="btn btn-danger"
              disabled={confirmText !== "계정 삭제" || deleteAccount.isPending}
              onClick={() => deleteAccount.mutate()}
            >
              <Trash2 size={14} /> 영구 삭제
            </button>
          </div>
          <ErrorText error={deleteAccount.error} />
        </div>
      </Section>
      <ErrorText error={me.error} />
    </div>
  );
}
