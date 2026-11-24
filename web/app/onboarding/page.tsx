"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  ArrowRight,
  Briefcase,
  Check,
  FileText,
  GraduationCap,
  HelpCircle,
  Plus,
  ShieldCheck,
} from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import { ErrorText } from "@/components/ErrorText";
import { GithubMark, LinkedinMark } from "@/components/icons";
import { Brand, Spinner, StatusDot, TypeIcon } from "@/components/ui";
import { api, patch, post, upload } from "@/lib/api";
import { env } from "@/lib/env";
import { supabaseBrowser } from "@/lib/supabase/client";
import { ITEM_TYPE_LABELS, type ImportRow, type Profile, type Proposal } from "@/lib/types";

const STEPS = ["목표", "동의", "자료 연결", "검토", "첫 결과"];

const GOALS = [
  { key: "grad_school", label: "대학원 진학", desc: "연구 경험과 Academic CV를 챙긴다.", icon: GraduationCap },
  { key: "employment", label: "취업", desc: "경력·프로젝트 중심 이력서를 챙긴다.", icon: Briefcase },
  { key: "undecided", label: "아직 모르겠다", desc: "둘 다 준비할 수 있게 기록부터 쌓는다.", icon: HelpCircle },
] as const;

const SOURCE_LABEL: Record<string, string> = { resume_file: "이력서", github: "GitHub", linkedin_zip: "LinkedIn" };

function useMe() {
  return useQuery({ queryKey: ["me"], queryFn: () => api<{ profile: Profile }>("/me") });
}

function StepGoal({ next }: { next: () => void }) {
  const qc = useQueryClient();
  const me = useMe();
  const [v, setV] = useState({ goal: "undecided", interests: "", target_roles: "", school: "", major: "", grade: "" });
  useEffect(() => {
    const p = me.data?.profile;
    if (!p) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setV({
      goal: p.goal,
      interests: p.interests.join(", "),
      target_roles: p.target_roles.join(", "),
      school: p.school ?? "",
      major: p.major ?? "",
      grade: p.grade ? String(p.grade) : "",
    });
  }, [me.data]);
  const split = (s: string) => s.split(",").map((x) => x.trim()).filter(Boolean);
  const save = useMutation({
    mutationFn: () =>
      patch("/me/profile", {
        goal: v.goal,
        interests: split(v.interests),
        target_roles: split(v.target_roles),
        school: v.school || null,
        major: v.major || null,
        grade: v.grade ? Number(v.grade) : null,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["me"] });
      next();
    },
  });
  const set = (k: keyof typeof v) => (e: React.ChangeEvent<HTMLInputElement>) => setV((s) => ({ ...s, [k]: e.target.value }));
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">무엇을 준비하고 있나요?</h1>
        <p className="mt-1 text-muted">목표에 맞춰 문서 형식과 항목 순서를 정한다. 나중에 설정에서 바꿀 수 있다.</p>
      </div>
      <div className="grid gap-3 sm:grid-cols-3">
        {GOALS.map(({ key, label, desc, icon: Icon }) => (
          <button
            key={key}
            onClick={() => setV((s) => ({ ...s, goal: key }))}
            className={`rounded-2xl border p-4 text-left transition ${v.goal === key ? "border-deep bg-mint/60 ring-2 ring-accent/50" : "border-line bg-white hover:border-deep/30"}`}
          >
            <Icon className="text-deep" size={22} />
            <p className="mt-3 font-semibold">{label}</p>
            <p className="mt-0.5 text-xs leading-relaxed text-muted">{desc}</p>
          </button>
        ))}
      </div>
      <div className="grid gap-4 sm:grid-cols-3">
        <label>
          <span className="label">학교</span>
          <input className="input" value={v.school} onChange={set("school")} />
        </label>
        <label>
          <span className="label">전공</span>
          <input className="input" value={v.major} onChange={set("major")} />
        </label>
        <label>
          <span className="label">학년</span>
          <input className="input" inputMode="numeric" value={v.grade} onChange={set("grade")} />
        </label>
        <label className="sm:col-span-3">
          <span className="label">관심 분야(쉼표로 나눈다)</span>
          <input className="input" value={v.interests} onChange={set("interests")} placeholder="예: 자연어처리, 백엔드, 데이터 분석" />
        </label>
        <label className="sm:col-span-3">
          <span className="label">목표 직무(쉼표로 나눈다)</span>
          <input className="input" value={v.target_roles} onChange={set("target_roles")} placeholder="예: 백엔드 개발자, ML 엔지니어" />
        </label>
      </div>
      <ErrorText error={save.error} />
      <button className="btn btn-primary" onClick={() => save.mutate()} disabled={save.isPending}>
        다음 <ArrowRight size={16} />
      </button>
    </div>
  );
}

function StepConsent({ next }: { next: () => void }) {
  const qc = useQueryClient();
  const me = useMe();
  const [agree, setAgree] = useState(false);
  const consent = useMutation({
    mutationFn: () => post("/me/consent"),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["me"] });
      next();
    },
  });
  const already = !!me.data?.profile.llm_consent_at;
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">기록 분석에 대한 동의</h1>
        <p className="mt-1 text-muted">일기와 올린 파일에서 항목을 찾으려면 외부 LLM API를 쓴다.</p>
      </div>
      <div className="card space-y-3 text-sm leading-relaxed">
        <p className="flex gap-2">
          <ShieldCheck className="shrink-0 text-deep" size={18} /> 일기 본문, 이력서, 증빙 파일의 내용이 분석을 위해 외부 LLM API로 전송된다.
        </p>
        <p className="text-muted">· 분석 결과는 바로 반영되지 않고 &lsquo;제안&rsquo;으로 들어오며, 직접 승인한 것만 포트폴리오에 쌓인다.</p>
        <p className="text-muted">· 원문에 없는 숫자·날짜·기관명은 저장하지 않도록 서버에서 한 번 더 확인한다.</p>
        <p className="text-muted">· 동의하지 않아도 일기를 쓰고 항목을 직접 입력할 수 있다.</p>
      </div>
      {already ? (
        <p className="flex items-center gap-2 text-sm text-deep">
          <Check size={16} /> 이미 동의했다.
        </p>
      ) : (
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" className="h-4 w-4 accent-[#224B46]" checked={agree} onChange={(e) => setAgree(e.target.checked)} />
          위 내용을 읽었고 동의한다.
        </label>
      )}
      <ErrorText error={consent.error} />
      <div className="flex gap-2">
        {already ? (
          <button className="btn btn-primary" onClick={next}>
            다음 <ArrowRight size={16} />
          </button>
        ) : (
          <button className="btn btn-primary" disabled={!agree || consent.isPending} onClick={() => consent.mutate()}>
            동의하고 다음 <ArrowRight size={16} />
          </button>
        )}
        {!already && (
          <button className="btn btn-ghost" onClick={next}>
            나중에 하기
          </button>
        )}
      </div>
    </div>
  );
}

function UploadCard({
  icon,
  title,
  desc,
  accept,
  path,
  disabled,
  onDone,
  help,
}: {
  icon: React.ReactNode;
  title: string;
  desc: string;
  accept: string;
  path: string;
  disabled?: string;
  onDone: () => void;
  help?: React.ReactNode;
}) {
  const ref = useRef<HTMLInputElement>(null);
  const send = useMutation({ mutationFn: (f: File) => upload(path, f), onSuccess: onDone });
  return (
    <div className="card flex flex-col gap-3">
      <div className="flex items-center gap-3">
        <span className="inline-flex h-10 w-10 items-center justify-center rounded-xl bg-mint text-deep">{icon}</span>
        <p className="font-semibold">{title}</p>
      </div>
      <p className="text-sm text-muted">{desc}</p>
      {help}
      <button className="btn mt-auto" disabled={!!disabled || send.isPending} onClick={() => ref.current?.click()}>
        {send.isPending ? "올리는 중이다" : "파일 고르기"}
      </button>
      {disabled && <p className="text-xs text-amber-700">{disabled}</p>}
      <input
        ref={ref}
        type="file"
        accept={accept}
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) send.mutate(f);
          e.target.value = "";
        }}
      />
      <ErrorText error={send.error} />
    </div>
  );
}

function QuickAdd() {
  const qc = useQueryClient();
  const [v, setV] = useState({ type: "certification", title: "", date: "", extra: "" });
  const add = useMutation({
    mutationFn: () => {
      const details =
        v.type === "certification" ? { issuer: v.extra } : v.type === "language_test" ? { test: v.title, score: v.extra } : { rank: v.extra };
      return post("/items", {
        type: v.type,
        title: v.title,
        start_date: v.type !== "award" && v.date ? v.date : null,
        end_date: v.type === "award" && v.date ? v.date : null,
        details: Object.fromEntries(Object.entries(details).filter(([, x]) => x)),
      });
    },
    onSuccess: () => {
      setV((s) => ({ ...s, title: "", date: "", extra: "" }));
      qc.invalidateQueries({ queryKey: ["items"] });
    },
  });
  const extraLabel = { certification: "발급기관", language_test: "점수·등급", award: "순위(대상, 우수상 등)" }[v.type];
  return (
    <div className="card space-y-3">
      <p className="font-semibold">자료가 없다면 직접 입력</p>
      <p className="text-sm text-muted">자격증·어학·수상처럼 정해진 값은 바로 넣어 두면 편하다.</p>
      <div className="grid gap-2 sm:grid-cols-[140px_1fr_150px_1fr_auto]">
        <select className="input" value={v.type} onChange={(e) => setV((s) => ({ ...s, type: e.target.value }))}>
          <option value="certification">자격증</option>
          <option value="language_test">어학</option>
          <option value="award">수상</option>
        </select>
        <input className="input" placeholder="이름(예: 정보처리기사)" value={v.title} onChange={(e) => setV((s) => ({ ...s, title: e.target.value }))} />
        <input className="input" type="date" value={v.date} onChange={(e) => setV((s) => ({ ...s, date: e.target.value }))} />
        <input className="input" placeholder={extraLabel} value={v.extra} onChange={(e) => setV((s) => ({ ...s, extra: e.target.value }))} />
        <button className="btn btn-primary" disabled={!v.title.trim() || add.isPending} onClick={() => add.mutate()}>
          <Plus size={14} /> 추가
        </button>
      </div>
      {add.isSuccess && <p className="text-sm text-deep">추가했다. 포트폴리오에 바로 들어갔다.</p>}
      <ErrorText error={add.error} />
    </div>
  );
}

function StepConnect({ next }: { next: () => void }) {
  const qc = useQueryClient();
  const me = useMe();
  const consented = !!me.data?.profile.llm_consent_at;
  const imports = useQuery({
    queryKey: ["imports"],
    queryFn: () => api<{ imports: ImportRow[] }>("/imports"),
    refetchInterval: (q) => (q.state.data?.imports.some((i) => ["queued", "running"].includes(i.status)) ? 2500 : false),
  });
  const refresh = () => qc.invalidateQueries({ queryKey: ["imports"] });
  const github = useMutation({
    mutationFn: async () => {
      const {
        data: { session },
      } = await supabaseBrowser().auth.getSession();
      if (!session?.provider_token) {
        await supabaseBrowser().auth.signInWithOAuth({
          provider: "github",
          options: {
            redirectTo: `${env.siteUrl}/auth/callback?next=${encodeURIComponent("/onboarding?step=3")}`,
            scopes: "read:user",
          },
        });
        return;
      }
      await post("/imports/github", { provider_token: session.provider_token });
    },
    onSuccess: refresh,
  });
  const needConsent = consented ? undefined : "이 기능을 쓰려면 앞 단계에서 LLM 처리에 동의해야 한다.";

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">이미 있는 기록을 가져와요</h1>
        <p className="mt-1 text-muted">가진 것만 고르면 된다. 가져온 내용은 모두 검토 큐로 들어간다.</p>
      </div>
      <div className="grid gap-4 md:grid-cols-3">
        <UploadCard
          icon={<FileText size={20} />}
          title="이력서 파일"
          desc="PDF나 DOCX 이력서에서 학력·경력·수상·자격증을 찾는다."
          accept=".pdf,.docx"
          path="/imports/resume"
          disabled={needConsent}
          onDone={refresh}
        />
        <div className="card flex flex-col gap-3">
          <div className="flex items-center gap-3">
            <span className="inline-flex h-10 w-10 items-center justify-center rounded-xl bg-ink text-white">
              <GithubMark size={20} />
            </span>
            <p className="font-semibold">GitHub</p>
          </div>
          <p className="text-sm text-muted">내 공개 저장소를 최근 순으로 30개까지 읽어 프로젝트 후보를 만든다.</p>
          <button className="btn mt-auto" disabled={!!needConsent || github.isPending} onClick={() => github.mutate()}>
            {github.isPending ? "요청하는 중이다" : "저장소 가져오기"}
          </button>
          {needConsent && <p className="text-xs text-amber-700">{needConsent}</p>}
          <ErrorText error={github.error} />
        </div>
        <UploadCard
          icon={<LinkedinMark size={20} />}
          title="LinkedIn"
          desc="LinkedIn 데이터 내보내기 ZIP에서 경력·학력·자격증을 읽는다."
          accept=".zip"
          path="/imports/linkedin"
          onDone={refresh}
          help={
            <a
              className="text-xs text-deep underline"
              href="https://www.linkedin.com/help/linkedin/answer/50191"
              target="_blank"
              rel="noopener noreferrer"
            >
              내보내기 ZIP 받는 방법
            </a>
          }
        />
      </div>

      {(imports.data?.imports.length ?? 0) > 0 && (
        <div className="card">
          <p className="section-title mb-2">가져오기 기록</p>
          <ul className="divide-y divide-line/70 text-sm">
            {imports.data?.imports.map((i) => (
              <li key={i.id} className="flex flex-wrap items-center gap-3 py-2.5">
                <span className="w-20 font-medium">{SOURCE_LABEL[i.source] ?? i.source}</span>
                <StatusDot status={i.status} />
                {i.status === "succeeded" && (
                  <span className="text-muted">
                    제안 {i.summary.items_proposed ?? 0}건{i.summary.merged ? ` · 합침 ${i.summary.merged}건` : ""}
                  </span>
                )}
                {i.error && <span className="text-red-700">{i.error}</span>}
                {!!i.summary.skipped?.length && (
                  <span className="w-full text-xs text-muted">건너뜀: {i.summary.skipped.join(", ")}</span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      <QuickAdd />

      <button className="btn btn-primary" onClick={next}>
        다음 <ArrowRight size={16} />
      </button>
    </div>
  );
}

function StepReview({ next }: { next: () => void }) {
  const qc = useQueryClient();
  const list = useQuery({
    queryKey: ["proposals"],
    queryFn: () => api<{ proposals: Proposal[] }>("/proposals?status=pending"),
    refetchInterval: 4000,
  });
  const refresh = () => ["proposals", "items", "pending-count"].forEach((k) => qc.invalidateQueries({ queryKey: [k] }));
  const act = useMutation({
    mutationFn: ({ id, ok }: { id: string; ok: boolean }) => post(`/proposals/${id}/${ok ? "accept" : "reject"}`),
    onSuccess: refresh,
  });
  const items = (list.data?.proposals ?? []).filter((p) => p.kind === "create_item" && p.item);
  const high = items.filter((p) => (p.confidence ?? 0) >= 0.8);
  const bulk = useMutation({
    mutationFn: () => post("/proposals/bulk-accept", { ids: high.map((p) => p.id) }),
    onSuccess: refresh,
  });
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">찾아낸 항목을 확인해요</h1>
        <p className="mt-1 text-muted">맞는 것은 승인하고, 틀린 것은 거절한다. 자세히 고치려면 검토 화면을 쓴다.</p>
      </div>
      <div className="flex flex-wrap gap-2">
        <button className="btn btn-primary" disabled={!high.length || bulk.isPending} onClick={() => bulk.mutate()}>
          <Check size={16} /> 신뢰도 높은 {high.length}건 모두 승인
        </button>
        <Link href="/review" className="btn">
          검토 화면에서 자세히 보기
        </Link>
      </div>
      <ErrorText error={bulk.error ?? act.error} />
      {list.isSuccess && items.length === 0 && (
        <p className="rounded-2xl bg-cream p-5 text-sm text-muted">
          지금 확인할 새 항목이 없다. 가져오기가 아직 진행 중이면 잠시 뒤 다시 채워진다.
        </p>
      )}
      <ul className="grid gap-3 md:grid-cols-2">
        {items.map((p) => (
          <li key={p.id} className="card flex items-start gap-3 p-4">
            <TypeIcon type={p.item!.type} />
            <div className="min-w-0 flex-1">
              <p className="font-semibold">{p.item!.title}</p>
              <p className="text-xs text-muted">
                {ITEM_TYPE_LABELS[p.item!.type]}
                {p.import_source ? ` · ${SOURCE_LABEL[p.import_source]}` : ""}
                {p.confidence !== null ? ` · 신뢰도 ${Math.round(p.confidence * 100)}%` : ""}
              </p>
              {p.quote && <p className="mt-1 line-clamp-2 text-xs text-muted">“{p.quote}”</p>}
            </div>
            <div className="flex flex-col gap-1">
              <button className="btn btn-primary btn-sm" onClick={() => act.mutate({ id: p.id, ok: true })}>
                승인
              </button>
              <button className="btn btn-ghost btn-sm" onClick={() => act.mutate({ id: p.id, ok: false })}>
                거절
              </button>
            </div>
          </li>
        ))}
      </ul>
      <button className="btn btn-primary" onClick={next}>
        다음 <ArrowRight size={16} />
      </button>
    </div>
  );
}

function StepResult() {
  const qc = useQueryClient();
  const router = useRouter();
  const me = useMe();
  const [handle, setHandle] = useState("");
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (me.data?.profile.handle) setHandle(me.data.profile.handle);
  }, [me.data]);
  const stats = useQuery({ queryKey: ["stats"], queryFn: () => api<{ items_total: number }>("/me/stats") });
  const publish = useMutation({
    mutationFn: () => patch("/me/profile", { handle, public_profile_enabled: true }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["me"] }),
  });
  const finish = useMutation({
    mutationFn: () => post("/me/onboarding/complete"),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["me"] });
      router.push("/dashboard");
    },
  });
  const p = me.data?.profile;
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">준비가 끝났어요</h1>
        <p className="mt-1 text-muted">지금 포트폴리오에는 항목 {stats.data?.items_total ?? 0}개가 있다. 이제 일기를 쓰면 계속 쌓인다.</p>
      </div>
      <div className="card space-y-3">
        <p className="font-semibold">공개 프로필 주소 정하기(선택)</p>
        <p className="text-sm text-muted">공개로 표시한 항목만 보인다. 항목은 기본적으로 비공개다.</p>
        <div className="flex flex-wrap gap-2">
          <div className="flex flex-1 items-center rounded-lg border border-line bg-cream/40 pl-3 text-sm text-muted">
            /p/
            <input
              className="w-full bg-transparent px-1 py-2 text-ink outline-none"
              value={handle}
              onChange={(e) => setHandle(e.target.value.toLowerCase())}
              placeholder="영문 소문자·숫자 3~30자"
            />
          </div>
          <button className="btn" disabled={!/^[a-z0-9_-]{3,30}$/.test(handle) || publish.isPending} onClick={() => publish.mutate()}>
            공개 켜기
          </button>
        </div>
        {p?.public_profile_enabled && p.handle && (
          <Link className="text-sm font-medium text-deep underline" href={`/p/${p.handle}`} target="_blank">
            내 공개 프로필 미리보기
          </Link>
        )}
        <ErrorText error={publish.error} />
      </div>
      <button className="btn btn-accent px-5 py-2.5" onClick={() => finish.mutate()} disabled={finish.isPending}>
        시작하기 <ArrowRight size={16} />
      </button>
      <ErrorText error={finish.error} />
    </div>
  );
}

function Onboarding() {
  const params = useSearchParams();
  const router = useRouter();
  const step = Math.min(5, Math.max(1, Number(params.get("step") ?? 1)));
  const go = (n: number) => router.push(`/onboarding?step=${n}`);
  return (
    <div className="min-h-screen bg-paper">
      <header className="border-b border-line/70 bg-white/70">
        <div className="mx-auto flex max-w-4xl items-center gap-4 px-6 py-4">
          <Brand className="text-lg" />
          <Link href="/dashboard" className="ml-auto text-sm text-muted hover:text-ink">
            건너뛰기
          </Link>
        </div>
      </header>
      <div className="mx-auto max-w-4xl px-6 py-10">
        <ol className="mb-10 flex items-center gap-2">
          {STEPS.map((s, i) => {
            const n = i + 1;
            const state = n < step ? "done" : n === step ? "now" : "todo";
            return (
              <li key={s} className="flex flex-1 items-center gap-2">
                <button
                  onClick={() => n < step && go(n)}
                  className={`inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-sm font-semibold ${
                    state === "done" ? "bg-deep text-white" : state === "now" ? "bg-accent text-ink" : "bg-ink/5 text-muted"
                  }`}
                >
                  {state === "done" ? <Check size={14} /> : n}
                </button>
                <span className={`hidden text-sm sm:inline ${state === "now" ? "font-semibold" : "text-muted"}`}>{s}</span>
                {n < STEPS.length && <span className={`h-0.5 flex-1 rounded ${n < step ? "bg-deep" : "bg-line"}`} />}
              </li>
            );
          })}
        </ol>
        {step > 1 && (
          <button className="mb-4 inline-flex items-center gap-1 text-sm text-muted hover:text-ink" onClick={() => go(step - 1)}>
            <ArrowLeft size={14} /> 이전
          </button>
        )}
        {step === 1 && <StepGoal next={() => go(2)} />}
        {step === 2 && <StepConsent next={() => go(3)} />}
        {step === 3 && <StepConnect next={() => go(4)} />}
        {step === 4 && <StepReview next={() => go(5)} />}
        {step === 5 && <StepResult />}
      </div>
    </div>
  );
}

export default function OnboardingPage() {
  return (
    <Suspense fallback={<Spinner />}>
      <Onboarding />
    </Suspense>
  );
}
