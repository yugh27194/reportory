import {
  ArrowRight,
  CalendarClock,
  ClipboardCheck,
  Compass,
  FileText,
  Globe,
  Heart,
  NotebookPen,
  Quote,
  Send,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import Link from "next/link";
import { redirect } from "next/navigation";
import { OliveTree } from "@/components/OliveTree";
import { RadarChart } from "@/components/SpecRadar";
import { Brand, TypeIcon } from "@/components/ui";
import { env } from "@/lib/env";
import { supabaseServer } from "@/lib/supabase/server";

const STEPS = [
  { level: 0, icon: NotebookPen, title: "일기처럼 쓴다", body: "오늘 한 일을 두세 문장으로. 폼도 형식도 없다." },
  {
    level: 1,
    icon: ClipboardCheck,
    title: "맞는 것만 담는다",
    body: "AI가 찾은 활동·프로젝트·수상 후보 중 맞는 것만 '추가'한다.",
  },
  {
    level: 3,
    icon: Sparkles,
    title: "나무가 자란다",
    body: "담을수록 화분의 싹이 올리브 나무로 자라고 가지가 뻗는다.",
  },
  { level: 4, icon: FileText, title: "필요할 때 꺼낸다", body: "지원할 곳에 맞춰 이력서·CV·포트폴리오를 바로 만든다." },
];

const TRUST = [
  {
    icon: Quote,
    title: "모든 문장에 근거",
    body: "경험마다 원문 일기 문장이 붙는다. 원문에 없는 숫자와 사실은 저장하지 않는다.",
  },
  { icon: Globe, title: "공개 프로필", body: "공개로 고른 경험만 담긴 나만의 프로필 주소를 갖는다." },
  { icon: ShieldCheck, title: "데이터는 내 것", body: "언제든 전부 내보내고, 계정을 지우면 모두 사라진다." },
];

const SAMPLE_RADAR = {
  axes: ["experience", "project", "activity", "award", "certification", "language_test", "publication"] as const,
  values: { experience: 1, project: 5, activity: 3, award: 2, certification: 1, language_test: 1, publication: 0 },
  target: { experience: 1, project: 4, activity: 2, award: 1, certification: 1, language_test: 1, publication: 0 },
};

function Showcase({
  eyebrow,
  title,
  body,
  children,
  flip,
}: {
  eyebrow: string;
  title: string;
  body: string;
  children: React.ReactNode;
  flip?: boolean;
}) {
  return (
    <div className="grid items-center gap-10 md:grid-cols-2">
      <div className={flip ? "md:order-2" : ""}>
        <p className="section-title">{eyebrow}</p>
        <h3 className="mt-2 text-2xl leading-snug font-bold sm:text-3xl">{title}</h3>
        <p className="mt-3 leading-relaxed text-muted">{body}</p>
      </div>
      <div className={flip ? "md:order-1" : ""}>{children}</div>
    </div>
  );
}

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
        <div className="relative mx-auto grid max-w-6xl items-center gap-12 px-6 pt-8 pb-20 lg:grid-cols-[1.05fr_1fr]">
          <div>
            <p className="inline-flex items-center gap-2 rounded-full border border-accent/30 bg-accent/10 px-3 py-1 text-xs text-accent">
              <Sparkles size={14} /> 대학생을 위한 기록 기반 포트폴리오
            </p>
            <h1 className="mt-6 text-4xl leading-tight font-bold tracking-tight sm:text-5xl">
              하루 세 줄이
              <br />
              <span className="text-accent">포트폴리오</span>로 자란다.
            </h1>
            <p className="mt-5 max-w-lg text-lg leading-relaxed text-white/70">
              일기처럼 남긴 기록에서 활동·프로젝트·수상을 찾아 근거와 함께 쌓는다. 쌓인 경험으로 나에게 맞는 공모전과
              인턴을 추천받고, 지원할 곳에 맞춘 이력서까지 바로 만든다.
            </p>
            <div className="mt-8 flex flex-wrap items-center gap-4">
              <Link href="/login" className="btn btn-accent px-5 py-2.5 text-base">
                무료로 시작하기 <ArrowRight size={18} />
              </Link>
              <span className="text-sm text-white/50">1분이면 첫 기록을 남길 수 있다</span>
            </div>
          </div>

          <div className="relative mx-auto w-full max-w-md">
            <div className="rounded-2xl bg-white/95 p-5 text-ink shadow-lift">
              <p className="text-xs font-semibold text-muted">11월 18일 일기</p>
              <p className="mt-2 text-sm leading-relaxed">
                오늘 OO 해커톤에서{" "}
                <mark className="rounded bg-accent/35 px-0.5 text-ink">팀원 3명과 FastAPI로 백엔드를 맡았다</mark>. 결과
                발표에서 <mark className="rounded bg-accent/35 px-0.5 text-ink">우수상을 받았다</mark>.
              </p>
            </div>
            <div className="relative z-10 -mt-3 ml-8 rounded-2xl border border-accent/40 bg-mint p-4 text-ink shadow-lift">
              <p className="text-xs font-semibold text-deep">이 일기에서 찾은 경험 2개</p>
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
                    <span className="rounded-lg bg-deep px-2 py-1 text-xs text-white">+ 추가</span>
                  </div>
                ))}
              </div>
            </div>
            <div className="pointer-events-none absolute -right-6 -bottom-16 hidden w-36 sm:block">
              <OliveTree level={3} />
            </div>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-6 py-20">
        <p className="section-title">어떻게 쓰나</p>
        <h2 className="mt-2 text-2xl font-bold sm:text-3xl">쓰고, 담고, 자라고, 꺼낸다</h2>
        <ol className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {STEPS.map((s, i) => (
            <li key={s.title} className="card flex flex-col overflow-hidden p-0">
              <div className="flex h-36 items-end justify-center bg-gradient-to-b from-mint/60 to-cream/60">
                <OliveTree level={s.level} sway={false} className="h-32" title="" />
              </div>
              <div className="p-5">
                <p className="flex items-center gap-2 text-sm font-bold text-accent-2">
                  <s.icon size={16} /> {String(i + 1).padStart(2, "0")}
                </p>
                <p className="mt-2 text-lg font-semibold">{s.title}</p>
                <p className="mt-1 text-sm leading-relaxed text-muted">{s.body}</p>
              </div>
            </li>
          ))}
        </ol>
      </section>

      <section className="border-y border-line/70 bg-white/60">
        <div className="mx-auto max-w-6xl space-y-20 px-6 py-20">
          <Showcase
            eyebrow="일기 책장"
            title="한 해가 한 칸, 한 달이 한 권"
            body="쓸수록 책이 두꺼워진다. 책을 펼치면 왼쪽에는 그달의 날짜, 오른쪽에는 그날의 기록이 있다. 지난 쪽을 도감처럼 넘기며 돌아본다."
          >
            <div className="rounded-3xl bg-gradient-to-b from-cream to-paper px-6 pt-8 pb-4">
              <div className="flex items-end justify-center gap-1.5">
                {[3, 6, 2, 9, 12, 4, 7, 10, 5, 8, 11, 0].map((d, i) => (
                  <span
                    key={i}
                    className="flex items-start justify-center rounded-[3px] pt-2 text-[9px] font-bold text-white/80 shadow-[inset_-4px_0_6px_rgba(0,0,0,.25)]"
                    style={{
                      width: d ? 14 + d * 2 : 12,
                      height: 96 + ((i * 37) % 4) * 6,
                      background: d ? ["#224b46", "#2a3d52", "#38b2a6", "#0e1b2a", "#2d625b"][i % 5] : "#c9c2b4",
                    }}
                  >
                    {i + 1}
                  </span>
                ))}
              </div>
              <div className="h-2.5 rounded-t bg-gradient-to-b from-[#b08a62] to-[#9b7653]" />
              <div className="h-3 rounded-b-md bg-gradient-to-b from-[#6e4f34] to-[#4a3424]" />
            </div>
          </Showcase>

          <Showcase
            flip
            eyebrow="모아보기 · 스펙 레이더"
            title="내 경험이 어디쯤인지 한눈에"
            body="모은 경험은 나무의 가지와 잎이 된다. 목표(개발 직무 취업, 대학원 진학 등)에 맞춘 기준선과 견주어 어느 쪽이 비어 있는지 레이더로 보여 준다."
          >
            <div className="card flex items-center justify-center gap-4 bg-gradient-to-b from-white to-cream/50">
              <OliveTree level={4} className="hidden h-52 w-40 sm:block" />
              <div className="w-full max-w-[280px]">
                <RadarChart axes={[...SAMPLE_RADAR.axes]} values={SAMPLE_RADAR.values} target={SAMPLE_RADAR.target} />
              </div>
            </div>
          </Showcase>

          <Showcase
            eyebrow="활동 추천 · 지원 관리"
            title="지금 나에게 맞는 공모전과 인턴"
            body="매일 모집 공고를 모아 내 목표와 경험에 맞춰 고른다. 왜 추천했는지 근거가 된 내 경험까지 보여 주고, 지원한 뒤에는 결과 발표까지 챙긴다."
          >
            <div className="card space-y-3">
              <div className="flex flex-wrap items-center gap-2">
                <span className="chip chip-ink">해커톤</span>
                <span className="inline-flex items-center gap-1 rounded-full bg-ink px-2.5 py-0.5 text-xs font-bold text-accent">
                  <CalendarClock size={12} /> D-5
                </span>
                <span className="chip">빈 경험 채우기</span>
              </div>
              <p className="text-lg font-bold">공공데이터 활용 AI 해커톤</p>
              <div className="rounded-xl bg-mint/70 p-3 text-sm text-deep">
                <p className="flex gap-2">
                  <Sparkles size={15} className="mt-0.5 shrink-0" />
                  &lsquo;OO 해커톤 백엔드&rsquo; 경험을 살릴 수 있다. 데이터 분석 경험을 더할 기회다.
                </p>
              </div>
              <div className="flex justify-end gap-2">
                <span className="btn btn-sm">
                  <Heart size={14} /> 관심
                </span>
                <span className="btn btn-primary btn-sm">
                  <Send size={14} /> 지원함
                </span>
              </div>
            </div>
          </Showcase>

          <Showcase
            flip
            eyebrow="목적별 문서"
            title="같은 경험, 지원할 곳에 맞는 모양으로"
            body="국문 이력서(표준 양식), 영문 Resume, Academic CV, 프로젝트 포트폴리오를 담아 둔 경험으로 만든다. 만든 문서는 화면에서 바로 고치고 PDF로 받는다."
          >
            <div className="grid grid-cols-2 gap-3">
              {[
                ["국문 이력서", "기업·공공기관"],
                ["영문 Resume", "외국계·해외"],
                ["Academic CV", "대학원·연구실"],
                ["포트폴리오", "개발·데이터 직무"],
              ].map(([t, d], i) => (
                <div
                  key={t}
                  className={`rounded-2xl border p-4 shadow-card ${i === 0 ? "border-ink bg-ink text-white" : "border-line bg-white"}`}
                >
                  <FileText size={18} className={i === 0 ? "text-accent" : "text-deep"} />
                  <p className="mt-6 font-semibold">{t}</p>
                  <p className={`text-xs ${i === 0 ? "text-white/60" : "text-muted"}`}>{d}</p>
                </div>
              ))}
            </div>
          </Showcase>
        </div>
      </section>

      <section className="mx-auto grid max-w-6xl gap-6 px-6 py-16 md:grid-cols-3">
        {TRUST.map(({ icon: Icon, title, body }) => (
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
      </section>

      <section className="px-6 pb-16">
        <div className="relative mx-auto max-w-6xl overflow-hidden rounded-3xl bg-ink px-8 py-12 text-white">
          <div className="pointer-events-none absolute -top-20 -right-10 h-64 w-64 rounded-full bg-deep blur-3xl" />
          <div className="relative flex flex-wrap items-center gap-6">
            <div className="mr-auto">
              <h2 className="text-2xl font-bold sm:text-3xl">오늘의 기록부터 시작해 보세요</h2>
              <p className="mt-2 text-white/60">화분 하나에서 시작한다. 경험이 쌓이면 나무가 된다.</p>
            </div>
            <Link href="/login" className="btn btn-accent px-5 py-2.5 text-base">
              <Compass size={18} /> 무료로 시작하기
            </Link>
          </div>
        </div>
      </section>

      <footer className="mx-auto flex max-w-6xl items-center px-6 py-10 text-sm text-muted">
        <Brand />
        <span className="ml-auto">기록이 근거가 되는 포트폴리오</span>
      </footer>
    </div>
  );
}
