"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useEffect, useState } from "react";
import { ErrorText } from "@/components/ErrorText";
import { api, patch, post } from "@/lib/api";
import type { Profile } from "@/lib/types";

const GOALS = { grad_school: "대학원 진학", employment: "취업", undecided: "아직 정하지 않았다" } as const;
const list = (s: string) =>
  s
    .split(",")
    .map((x) => x.trim())
    .filter(Boolean);

export default function SettingsPage() {
  const qc = useQueryClient();
  const me = useQuery({ queryKey: ["me"], queryFn: () => api<{ profile: Profile }>("/me") });
  const [form, setForm] = useState({
    display_name: "",
    display_name_en: "",
    handle: "",
    goal: "undecided" as Profile["goal"],
    interests: "",
    target_roles: "",
    school: "",
    major: "",
    grade: "",
    email_public: "",
  });
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    const p = me.data?.profile;
    if (!p) return;
    // 서버 값을 폼 초기값으로 한 번 옮긴다.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setForm({
      display_name: p.display_name ?? "",
      display_name_en: p.display_name_en ?? "",
      handle: p.handle ?? "",
      goal: p.goal,
      interests: p.interests.join(", "),
      target_roles: p.target_roles.join(", "),
      school: p.school ?? "",
      major: p.major ?? "",
      grade: p.grade ? String(p.grade) : "",
      email_public: p.email_public ?? "",
    });
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
        handle: form.handle || null,
        goal: form.goal,
        interests: list(form.interests),
        target_roles: list(form.target_roles),
        school: form.school || null,
        major: form.major || null,
        grade: form.grade ? Number(form.grade) : null,
        email_public: form.email_public || null,
      }),
    onSuccess: done,
  });
  const togglePublic = useMutation({
    mutationFn: (on: boolean) => patch("/me/profile", { public_profile_enabled: on }),
    onSuccess: done,
  });
  const consent = useMutation({ mutationFn: () => post("/me/consent"), onSuccess: done });

  const p = me.data?.profile;
  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    setSaved(false);
    setForm((f) => ({ ...f, [k]: e.target.value }));
  };

  return (
    <div className="max-w-2xl space-y-6">
      <h1 className="text-lg font-semibold">설정</h1>
      <section className="card space-y-3">
        <h2 className="font-medium">프로필</h2>
        <form
          className="grid gap-3 sm:grid-cols-2"
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
            <span className="label">공개 프로필 주소(handle)</span>
            <input className="input" value={form.handle} onChange={set("handle")} placeholder="영문 소문자·숫자 3~30자" />
          </label>
          <label>
            <span className="label">공개 이메일</span>
            <input className="input" type="email" value={form.email_public} onChange={set("email_public")} />
          </label>
          <div className="flex items-center gap-3 sm:col-span-2">
            <button className="btn btn-primary" disabled={save.isPending}>
              저장
            </button>
            {saved && <span className="text-sm text-zinc-500">저장했다.</span>}
          </div>
        </form>
        <ErrorText error={save.error} />
      </section>

      <section className="card space-y-2">
        <h2 className="font-medium">공개 프로필</h2>
        {p?.public_profile_enabled && p.handle ? (
          <p className="text-sm">
            공개 중이다.{" "}
            <Link className="text-brand underline" href={`/p/${p.handle}`} target="_blank">
              /p/{p.handle}
            </Link>
          </p>
        ) : (
          <p className="text-sm text-zinc-500">꺼져 있다. 공개로 표시한 승인 항목만 보인다.</p>
        )}
        <button
          className="btn"
          disabled={togglePublic.isPending || !p}
          onClick={() => togglePublic.mutate(!p?.public_profile_enabled)}
        >
          {p?.public_profile_enabled ? "공개 끄기" : "공개 켜기"}
        </button>
        <ErrorText error={togglePublic.error} />
      </section>

      <section className="card space-y-2">
        <h2 className="font-medium">LLM 처리 동의</h2>
        {p?.llm_consent_at ? (
          <p className="text-sm text-zinc-500">
            {new Date(p.llm_consent_at).toLocaleDateString("ko-KR")}에 동의했다. 일기는 분석을 위해 외부 LLM API로 전송된다.
          </p>
        ) : (
          <>
            <p className="text-sm text-zinc-500">
              동의하면 일기 내용이 분석을 위해 외부 LLM API로 전송된다. 동의하기 전에는 일기 분석을 쓸 수 없다.
            </p>
            <button className="btn" onClick={() => consent.mutate()} disabled={consent.isPending}>
              동의하기
            </button>
          </>
        )}
      </section>
      <ErrorText error={me.error} />
    </div>
  );
}
