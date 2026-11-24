"use client";

import { Mail } from "lucide-react";
import { GithubMark } from "@/components/icons";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { Brand } from "@/components/ui";
import { env } from "@/lib/env";
import { supabaseBrowser } from "@/lib/supabase/client";

function LoginForm() {
  const params = useSearchParams();
  const next = params.get("next") ?? "/dashboard";
  const [email, setEmail] = useState("");
  const [state, setState] = useState<"idle" | "sending" | "sent">("idle");
  const [error, setError] = useState<string | null>(params.get("error"));
  const redirectTo = `${env.siteUrl}/auth/callback?next=${encodeURIComponent(next)}`;

  async function sendLink(e: React.FormEvent) {
    e.preventDefault();
    setState("sending");
    setError(null);
    const { error } = await supabaseBrowser().auth.signInWithOtp({
      email,
      options: { emailRedirectTo: redirectTo },
    });
    if (error) {
      setError("로그인 링크를 보내지 못했다. 초대받은 이메일인지 확인하고 다시 시도해 보세요.");
      setState("idle");
    } else {
      setState("sent");
    }
  }

  async function github() {
    await supabaseBrowser().auth.signInWithOAuth({
      provider: "github",
      options: { redirectTo, scopes: "read:user" },
    });
  }

  return (
    <main className="grid min-h-screen lg:grid-cols-2">
      <section className="relative hidden overflow-hidden bg-ink p-12 text-white lg:flex lg:flex-col">
        <div className="pointer-events-none absolute -right-32 -bottom-32 h-96 w-96 rounded-full bg-deep/70 blur-3xl" />
        <Brand dark className="text-2xl" />
        <div className="relative mt-auto max-w-md">
          <p className="text-3xl leading-snug font-bold">
            오늘의 기록이
            <br />
            내일의 <span className="text-accent">이력서</span>가 된다.
          </p>
          <p className="mt-4 text-white/60">일기 한 편이면 충분하다. 정리는 re:portory가 돕는다.</p>
        </div>
      </section>
      <section className="flex items-center justify-center p-6">
        <div className="w-full max-w-sm space-y-6">
          <div>
            <Brand className="text-xl lg:hidden" />
            <h1 className="mt-6 text-2xl font-bold lg:mt-0">로그인</h1>
            <p className="mt-1 text-sm text-muted">처음이면 로그인과 함께 계정이 만들어진다.</p>
          </div>
          <button className="btn btn-primary w-full py-2.5" onClick={github}>
            <GithubMark size={18} /> GitHub로 계속하기
          </button>
          <div className="flex items-center gap-3 text-xs text-muted">
            <span className="h-px flex-1 bg-line" /> 또는 이메일 <span className="h-px flex-1 bg-line" />
          </div>
          {state === "sent" ? (
            <p className="rounded-xl bg-mint p-4 text-sm text-deep">
              {email}로 로그인 링크를 보냈다. 메일함에서 링크를 눌러 주세요.
            </p>
          ) : (
            <form onSubmit={sendLink} className="space-y-3">
              <label className="label" htmlFor="email">
                이메일
              </label>
              <input
                id="email"
                type="email"
                required
                className="input"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
              />
              <button className="btn w-full py-2.5" disabled={state === "sending"}>
                <Mail size={16} /> {state === "sending" ? "보내는 중이다" : "로그인 링크 받기"}
              </button>
            </form>
          )}
          {error && <p className="text-sm text-red-700">{error}</p>}
          <p className="text-xs text-muted">지금은 초대받은 이메일만 가입할 수 있다.</p>
        </div>
      </section>
    </main>
  );
}

export default function LoginPage() {
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  );
}
