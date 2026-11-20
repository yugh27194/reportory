"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { SERVICE_NAME, env } from "@/lib/env";
import { supabaseBrowser } from "@/lib/supabase/client";

function LoginForm() {
  const params = useSearchParams();
  const next = params.get("next") ?? "/journal";
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
      setError("로그인 링크를 보내지 못했다. 이메일 주소를 확인하고 다시 시도해 보세요.");
      setState("idle");
    } else {
      setState("sent");
    }
  }

  async function github() {
    await supabaseBrowser().auth.signInWithOAuth({ provider: "github", options: { redirectTo } });
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-sm flex-col justify-center gap-6 px-6">
      <div>
        <p className="text-sm font-semibold text-brand">{SERVICE_NAME}</p>
        <h1 className="mt-1 text-2xl font-bold">로그인</h1>
      </div>
      {state === "sent" ? (
        <p className="card text-sm">
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
          <button className="btn btn-primary w-full" disabled={state === "sending"}>
            {state === "sending" ? "보내는 중이다" : "로그인 링크 받기"}
          </button>
        </form>
      )}
      <button className="btn w-full" onClick={github}>
        GitHub로 로그인
      </button>
      {error && <p className="text-sm text-red-700">{error}</p>}
      <p className="text-xs text-zinc-500">초기에는 초대받은 이메일만 가입할 수 있다.</p>
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
