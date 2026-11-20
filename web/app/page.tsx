import Link from "next/link";
import { redirect } from "next/navigation";
import { SERVICE_NAME, env } from "@/lib/env";
import { supabaseServer } from "@/lib/supabase/server";

export default async function Landing() {
  if (env.supabaseUrl) {
    const supabase = await supabaseServer();
    const {
      data: { user },
    } = await supabase.auth.getUser();
    if (user) redirect("/journal");
  }
  return (
    <main className="mx-auto flex min-h-screen max-w-2xl flex-col justify-center gap-6 px-6">
      <p className="text-sm font-semibold tracking-wide text-brand">{SERVICE_NAME}</p>
      <h1 className="text-3xl font-bold leading-tight">
        일기처럼 쓰면, 포트폴리오가 쌓인다.
      </h1>
      <ul className="space-y-2 text-zinc-600">
        <li>오늘 한 일을 일기로 쓰면 활동, 프로젝트, 수상 기록을 찾아 제안한다.</li>
        <li>제안은 직접 확인하고 승인한 것만 포트폴리오에 들어간다.</li>
        <li>모든 항목은 원문 일기의 문장과 연결돼 언제든 근거를 확인할 수 있다.</li>
      </ul>
      <div>
        <Link href="/login" className="btn btn-primary">
          시작하기
        </Link>
      </div>
    </main>
  );
}
