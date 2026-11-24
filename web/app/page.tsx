import { ArrowRight, FileText, Globe, Quote, ShieldCheck, Sparkles } from "lucide-react";
import Link from "next/link";
import { redirect } from "next/navigation";
import { Brand, TypeIcon } from "@/components/ui";
import { env } from "@/lib/env";
import { supabaseServer } from "@/lib/supabase/server";

const STEPS = [
  { n: "01", title: "일기처럼 쓴다", body: "오늘 한 일을 편하게 적는다. 폼을 채울 필요가 없다." },
  { n: "02", title: "제안을 확인한다", body: "활동·프로젝트·수상 후보를 찾아 원문 문장과 함께 보여 준다." },
  { n: "03", title: "승인한 것만 쌓인다", body: "고르고 고친 항목만 포트폴리오와 문서에 들어간다." },
];

const FEATURES = [
  { icon: Quote, title: "모든 문장에 근거", body: "항목마다 원문 일기·이력서·증빙 문장이 연결된다. 원문에 없는 숫자는 저장하지 않는다." },
  { icon: FileText, title: "목적별 문서", body: "국문 이력서, 영문 Resume, Academic CV, 프로젝트 포트폴리오를 같은 데이터에서 만든다." },
  { icon: Globe, title: "공개 프로필", body: "공개로 고른 항목만 담긴 프로필 주소를 하나 갖는다." },
  { icon: ShieldCheck, title: "데이터는 내 것", body: "언제든 JSON Resume로 전부 내보내고 계정을 지울 수 있다." },
];

export default async function Landing() {
  if (env.supabaseUrl) {
    const supabase = await supabaseServer();
    const {
      data: { user },
    } = await supabase.auth.getUser();
    if (user) redirect("/dashboard");
  }
  return (
    <div className="min-h-screen bg-paper">
      <section className="relative overflow-hidden bg-ink text-white">
        <div className="pointer-events-none absolute -top-40 -right-40 h-[520px] w-[520px] rounded-full bg-deep/60 blur-3xl" />
        <div className="pointer-events-none absolute -bottom-48 left-1/3 h-80 w-80 rounded-full bg-accent/15 blur-3xl" />
        <header className="relative mx-auto flex max-w-6xl items-center px-6 py-6">
          <Brand dark className="text-xl" />
          <Link href="/login" className="ml-auto text-sm text-white/70 hover:text-white">
            로그인
          </Link>
        </header>
        <div className="relative mx-auto grid max-w-6xl items-center gap-12 px-6 pt-10 pb-24 lg:grid-cols-[1.1fr_1fr]">
          <div>
            <p className="inline-flex items-center gap-2 rounded-full border border-accent/30 bg-accent/10 px-3 py-1 text-xs text-accent">
              <Sparkles size={14} /> 대학생을 위한 기록 기반 포트폴리오
            </p>
            <h1 className="mt-6 text-4xl leading-tight font-bold tracking-tight sm:text-5xl">
              일기처럼 쓰면,
              <br />
              <span className="text-accent">포트폴리오</span>가 쌓인다.
            </h1>
            <p className="mt-5 max-w-lg text-lg leading-relaxed text-white/70">
              매일의 기록에서 활동·프로젝트·수상을 찾아내고, 근거 문장과 함께 정리한다. 지원할 곳에 맞춰 이력서와
              CV도 바로 만든다.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link href="/login" className="btn btn-accent px-5 py-2.5 text-base">
                무료로 시작하기 <ArrowRight size={18} />
              </Link>
            </div>
          </div>

          <div className="relative mx-auto w-full max-w-md">
            <div className="rounded-2xl bg-white/95 p-5 text-ink shadow-lift">
              <p className="text-xs font-semibold text-muted">11월 18일 일기</p>
              <p className="mt-2 text-sm leading-relaxed">
                오늘 OO 해커톤에서{" "}
                <mark className="rounded bg-accent/35 px-0.5 text-ink">팀원 3명과 FastAPI로 백엔드를 맡았다</mark>.
                결과 발표에서 <mark className="rounded bg-accent/35 px-0.5 text-ink">우수상을 받았다</mark>.
              </p>
            </div>
            <div className="relative z-10 -mt-3 ml-8 rounded-2xl border border-accent/40 bg-mint p-4 text-ink shadow-lift">
              <p className="text-xs font-semibold text-deep">제안 2건을 찾았다</p>
              <div className="mt-3 space-y-2">
                {[
                  { t: "project" as const, title: "OO 해커톤 백엔드", sub: "FastAPI · 팀 3명" },
                  { t: "award" as const, title: "OO 해커톤 우수상", sub: "수상" },
                ].map((x) => (
                  <div key={x.title} className="flex items-center gap-3 rounded-xl bg-white p-2.5">
                    <TypeIcon type={x.t} size="sm" />
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-semibold">{x.title}</p>
                      <p className="text-xs text-muted">{x.sub}</p>
                    </div>
                    <span className="rounded-lg bg-deep px-2 py-1 text-xs text-white">승인</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-6 py-20">
        <p className="section-title">어떻게 쓰나</p>
        <div className="mt-6 grid gap-5 md:grid-cols-3">
          {STEPS.map((s) => (
            <div key={s.n} className="card">
              <p className="text-3xl font-bold text-accent">{s.n}</p>
              <p className="mt-3 text-lg font-semibold">{s.title}</p>
              <p className="mt-1 text-sm leading-relaxed text-muted">{s.body}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="bg-cream/70">
        <div className="mx-auto grid max-w-6xl gap-5 px-6 py-20 sm:grid-cols-2">
          {FEATURES.map(({ icon: Icon, title, body }) => (
            <div key={title} className="flex gap-4">
              <span className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-ink text-accent">
                <Icon size={20} />
              </span>
              <div>
                <p className="font-semibold">{title}</p>
                <p className="mt-1 text-sm leading-relaxed text-muted">{body}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      <footer className="mx-auto flex max-w-6xl items-center px-6 py-10 text-sm text-muted">
        <Brand />
        <span className="ml-auto">기록이 근거가 되는 포트폴리오</span>
      </footer>
    </div>
  );
}
