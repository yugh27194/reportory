"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, ArrowRight, BookOpen, ClipboardCheck, FileText, NotebookPen, Sparkles, X } from "lucide-react";
import { usePathname, useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useLayoutEffect, useState } from "react";
import { OliveTree } from "@/components/OliveTree";
import { post } from "@/lib/api";

/**
 * 첫 사용 안내(튜토리얼). 실제 화면의 요소(data-tour)를 하나씩 비추며 흐름을 보여 준다.
 * 대상 요소가 없거나 보이지 않으면(모바일 서랍 메뉴, 빈 화면) 가운데 카드로 보여 준다.
 */

type Step = {
  route: string;
  targets?: string[]; // data-tour 값. 앞에서부터 처음 보이는 것을 비춘다
  title: string;
  body: React.ReactNode;
  kind?: "welcome" | "finish";
};

const STEPS: Step[] = [
  {
    route: "/dashboard",
    kind: "welcome",
    title: "re:portory에 온 걸 환영한다",
    body: "하루 몇 줄의 기록이 근거 있는 포트폴리오가 된다. 1분이면 둘러볼 수 있다.",
  },
  {
    route: "/journal",
    targets: ["editor"],
    title: "1. 오늘 한 일을 편하게 적는다",
    body: "형식은 없다. 수업 과제, 동아리, 대회, 공부 무엇이든 좋다. 저장하면 AI가 기록에서 경험 후보를 찾아 바로 아래에 보여 준다.",
  },
  {
    route: "/journal",
    targets: ["bookshelf"],
    title: "2. 쓸수록 책이 두꺼워진다",
    body: "한 칸이 한 해, 책 한 권이 한 달이다. 책을 눌러 지난 날을 펼쳐 보고, ← → 키로 넘겨 본다.",
  },
  {
    route: "/journal",
    targets: ["review-help", "editor"],
    title: "3. 맞는 것만 골라 담는다",
    body: "AI가 찾은 후보는 바로 저장되지 않는다. 일기 아래에서 '추가'를 누른 것만 내 경험으로 쌓이고, 아니면 'X'로 뺀다. 원문에 없는 사실은 만들지 않는다.",
  },
  {
    route: "/dashboard",
    targets: ["growth"],
    title: "4. 나무가 자란다",
    body: "경험을 담고 기록한 날이 늘수록 화분의 싹이 올리브 나무로 자란다. 옆의 레이더는 목표 기준선(주홍)과 지금 모은 경험(파랑)을 견준다.",
  },
  {
    route: "/portfolio",
    targets: ["tree", "page-header"],
    title: "5. 모아보기",
    body: "모은 경험을 나무로 본다. 가지는 경험 유형, 잎 하나가 경험 하나다. 잎을 누르면 근거가 된 일기 문장까지 볼 수 있다.",
  },
  {
    route: "/recommendations",
    targets: ["page-header"],
    title: "6. 나에게 맞는 활동 추천",
    body: "매일 모집 공고를 모아 목표와 경험에 맞춰 고른다. 관심·지원을 누르면 지원 관리 보드에서 결과까지 이어서 챙긴다.",
  },
  {
    route: "/documents",
    targets: ["page-header"],
    title: "7. 필요할 때 문서로 꺼낸다",
    body: "국문 이력서, 영문 Resume, Academic CV, 포트폴리오를 담아 둔 경험으로 만든다. 만든 문서는 화면에서 바로 고칠 수 있다.",
  },
  {
    route: "/journal",
    kind: "finish",
    title: "이제 첫 기록을 남겨 보자",
    body: "오늘 한 일을 두세 문장만 적어도 된다. 무엇을 써야 할지 모르겠다면 예시로 먼저 써 본다.",
  },
];

const KEY = "rp-tour-step";

type TourCtx = { start: () => void; active: boolean };
const Ctx = createContext<TourCtx>({ start: () => {}, active: false });
export const useTour = () => useContext(Ctx);

function readStep(): number | null {
  try {
    const v = sessionStorage.getItem(KEY);
    return v === null ? null : Number(v);
  } catch {
    return null;
  }
}
function writeStep(n: number | null) {
  try {
    if (n === null) sessionStorage.removeItem(KEY);
    else sessionStorage.setItem(KEY, String(n));
  } catch {}
}

function findTarget(targets: string[] | undefined): HTMLElement | null {
  for (const t of targets ?? []) {
    const els = Array.from(document.querySelectorAll<HTMLElement>(`[data-tour="${t}"]`));
    const el = els.find((e) => {
      const r = e.getBoundingClientRect();
      return r.width > 0 && r.height > 0;
    });
    if (el) return el;
  }
  return null;
}

export function TourProvider({ autoStart, children }: { autoStart: boolean; children: React.ReactNode }) {
  const [step, setStep] = useState<number | null>(null);
  const qc = useQueryClient();
  const done = useMutation({
    mutationFn: (completed: boolean) => post("/me/tutorial", { completed }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["me"] }),
  });

  // 새로 고침해도 진행 중인 단계를 이어 간다. 처음이면 자동으로 시작한다.
  useEffect(() => {
    const saved = readStep();
    const next = saved ?? (autoStart ? 0 : null);
    if (next !== null) {
      // 외부 저장소(sessionStorage)에서 읽은 값을 반영한다.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setStep(next);
    }
  }, [autoStart]);

  const go = useCallback((n: number | null) => {
    writeStep(n);
    setStep(n);
  }, []);
  const finish = useCallback(() => {
    go(null);
    done.mutate(true);
  }, [go, done]);
  const start = useCallback(() => {
    done.mutate(false);
    go(0);
  }, [go, done]);

  return (
    <Ctx.Provider value={{ start, active: step !== null }}>
      {children}
      {step !== null && STEPS[step] && (
        <TourStep key={step} index={step} onPrev={() => go(step - 1)} onNext={() => go(step + 1)} onClose={finish} />
      )}
    </Ctx.Provider>
  );
}

type Rect = { top: number; left: number; width: number; height: number };

function TourStep({
  index,
  onPrev,
  onNext,
  onClose,
}: {
  index: number;
  onPrev: () => void;
  onNext: () => void;
  onClose: () => void;
}) {
  const s = STEPS[index];
  const path = usePathname();
  const router = useRouter();
  const [rect, setRect] = useState<Rect | null>(null);
  const [ready, setReady] = useState(false);
  const last = index === STEPS.length - 1;

  useEffect(() => {
    if (path !== s.route) router.push(s.route);
  }, [path, s.route, router]);

  // 대상 요소가 그려질 때까지 잠깐 기다렸다가(최대 2.5초) 위치를 잰다.
  useLayoutEffect(() => {
    if (path !== s.route) return;
    let tries = 0;
    let timer: ReturnType<typeof setTimeout>;
    const measure = () => {
      const el = findTarget(s.targets);
      if (el) {
        const r = el.getBoundingClientRect();
        setRect((prev) =>
          prev && prev.top === r.top && prev.left === r.left && prev.width === r.width && prev.height === r.height
            ? prev
            : { top: r.top, left: r.left, width: r.width, height: r.height },
        );
      } else {
        setRect(null);
      }
    };
    let poll: ReturnType<typeof setInterval> | undefined;
    const locate = () => {
      const el = findTarget(s.targets);
      if (el || !s.targets?.length || tries > 25) {
        if (el) {
          // 휴대폰에서는 안내 카드가 아래 절반을 덮으므로 대상을 위쪽에 둔다.
          const small = window.innerWidth < 640;
          el.scrollIntoView({ block: small ? "start" : "center", behavior: "instant" as ScrollBehavior });
          if (small) window.scrollBy(0, -72);
        }
        measure();
        setReady(true);
        // 책 펼치기·쪽 넘기기 애니메이션과 늦게 그려지는 내용 때문에 자리가 바뀌므로 계속 다시 잰다.
        poll = setInterval(measure, 200);
        return;
      }
      tries += 1;
      timer = setTimeout(locate, 100);
    };
    locate();
    window.addEventListener("resize", measure);
    window.addEventListener("scroll", measure, true);
    return () => {
      clearTimeout(timer);
      clearInterval(poll);
      window.removeEventListener("resize", measure);
      window.removeEventListener("scroll", measure, true);
    };
  }, [path, s.route, s.targets]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (e.key === "ArrowRight" && !last) onNext();
      if (e.key === "ArrowLeft" && index > 0) onPrev();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [index, last, onClose, onNext, onPrev]);

  if (!ready) return <div className="fixed inset-0 z-[80] bg-ink/40" />;

  const pad = 8;
  const spot = rect && {
    top: rect.top - pad,
    left: rect.left - pad,
    width: rect.width + pad * 2,
    height: rect.height + pad * 2,
  };
  // 카드 위치: 대상 아래가 넉넉하면 아래, 아니면 위. 대상이 없으면 가운데.
  let cardStyle: React.CSSProperties | undefined;
  if (spot && typeof window !== "undefined" && window.innerWidth >= 640) {
    const w = 360;
    const left = Math.min(Math.max(16, spot.left), window.innerWidth - w - 16);
    const below = spot.top + spot.height + 14;
    const fitsBelow = below + 240 < window.innerHeight;
    cardStyle = fitsBelow ? { top: below, left, width: w } : { top: Math.max(16, spot.top - 254), left, width: w };
  }

  return (
    <div className="fixed inset-0 z-[80]" role="dialog" aria-modal="true" aria-label={s.title}>
      {spot ? (
        <div
          className="pointer-events-none absolute rounded-2xl ring-2 ring-accent transition-all duration-300"
          style={{ ...spot, boxShadow: "0 0 0 9999px rgba(14,27,42,.62)" }}
        />
      ) : (
        <div className="absolute inset-0 bg-ink/60 backdrop-blur-[2px]" />
      )}
      <div
        className={
          cardStyle
            ? "tour-card absolute"
            : "tour-card absolute inset-x-4 bottom-4 mx-auto max-w-md sm:inset-x-0 sm:top-1/2 sm:bottom-auto sm:-translate-y-1/2"
        }
        style={cardStyle}
      >
        <div className="overflow-hidden rounded-2xl bg-white shadow-lift">
          {s.kind === "welcome" && <Welcome />}
          {s.kind === "finish" && (
            <div className="flex justify-center bg-gradient-to-b from-mint to-cream/60 pt-4">
              <OliveTree level={1} className="h-32" />
            </div>
          )}
          <div className="p-5">
            <div className="mb-2 flex items-center gap-2">
              <span className="text-xs font-semibold text-deep">
                {index + 1} / {STEPS.length}
              </span>
              <span className="flex flex-1 gap-1">
                {STEPS.map((_, i) => (
                  <span key={i} className={`h-1 flex-1 rounded-full ${i <= index ? "bg-accent" : "bg-line"}`} />
                ))}
              </span>
              <button className="rounded p-1 text-muted hover:text-ink" onClick={onClose} aria-label="안내 닫기">
                <X size={16} />
              </button>
            </div>
            <h2 className="text-lg font-bold">{s.title}</h2>
            <p className="mt-1.5 text-sm leading-relaxed text-muted">{s.body}</p>
            {s.kind === "finish" ? (
              <div className="mt-4 grid gap-2 sm:grid-cols-2">
                <button
                  className="btn btn-primary"
                  onClick={() => {
                    onClose();
                    window.dispatchEvent(new CustomEvent("rp:sample-entry"));
                  }}
                >
                  <Sparkles size={15} /> 예시로 써 보기
                </button>
                <button
                  className="btn"
                  onClick={() => {
                    onClose();
                    document.querySelector<HTMLElement>('[data-tour="editor"] textarea')?.focus();
                  }}
                >
                  <NotebookPen size={15} /> 직접 쓰기
                </button>
              </div>
            ) : (
              <div className="mt-4 flex items-center gap-2">
                {index === 0 ? (
                  <button className="btn btn-ghost btn-sm text-muted" onClick={onClose}>
                    건너뛰기
                  </button>
                ) : (
                  <button className="btn btn-ghost btn-sm" onClick={onPrev}>
                    <ArrowLeft size={14} /> 이전
                  </button>
                )}
                <button className="btn btn-primary ml-auto" onClick={onNext}>
                  {index === 0 ? "둘러보기" : "다음"} <ArrowRight size={15} />
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function Welcome() {
  const steps = [
    { icon: NotebookPen, label: "기록한다" },
    { icon: ClipboardCheck, label: "골라 담는다" },
    { icon: BookOpen, label: "쌓여 자란다" },
    { icon: FileText, label: "문서로 꺼낸다" },
  ];
  return (
    <div className="relative overflow-hidden bg-ink px-5 pt-6 pb-5 text-white">
      <div className="pointer-events-none absolute -top-16 -right-16 h-48 w-48 rounded-full bg-deep blur-3xl" />
      <div className="relative flex items-end justify-center gap-1">
        {[0, 1, 2, 4].map((lv) => (
          <OliveTree key={lv} level={lv} sway={false} className={`tour-grow h-20 w-16`} title="" />
        ))}
      </div>
      <ol className="relative mt-4 grid grid-cols-4 gap-1 text-center text-[11px] text-white/80">
        {steps.map(({ icon: Icon, label }) => (
          <li key={label} className="flex flex-col items-center gap-1">
            <Icon size={16} className="text-accent" />
            {label}
          </li>
        ))}
      </ol>
    </div>
  );
}
