"use client";

import { useEffect } from "react";
import { LogoMark } from "@/components/Logo";

export const INTRO_KEY = "rp-intro-seen";

/**
 * 첫 접속 애니메이션. 재생 여부는 layout의 인라인 스크립트가 그리기 전에 정한다
 * (html[data-intro="play"]). 브라우저 세션마다 한 번, 움직임 줄이기 설정이면 재생하지 않는다.
 */
export function IntroSplash() {
  useEffect(() => {
    const html = document.documentElement;
    if (html.dataset.intro !== "play") return;
    const done = () => {
      delete html.dataset.intro;
      try {
        sessionStorage.setItem(INTRO_KEY, "1");
      } catch {
        // 저장소를 쓸 수 없어도 애니메이션은 끝낸다.
      }
    };
    const t = window.setTimeout(done, 2700);
    return () => window.clearTimeout(t);
  }, []);

  return (
    <div
      className="intro-splash"
      aria-hidden
      onClick={() => {
        delete document.documentElement.dataset.intro;
        try {
          sessionStorage.setItem(INTRO_KEY, "1");
        } catch {}
      }}
    >
      <div className="flex flex-col items-center gap-5">
        <LogoMark size={112} animated className="intro-logo" />
        <p className="intro-word text-3xl font-bold tracking-tight text-white">
          re<span className="text-accent">:</span>portory
        </p>
        <p className="intro-tag text-sm text-white/60">기록이 근거가 되는 포트폴리오</p>
      </div>
    </div>
  );
}

/** 그리기 전에 실행되는 스크립트: 재생할지 정한다(공개 프로필·로그인 콜백은 제외). */
export const introBootScript = `try{var p=location.pathname;if(!/^\\/(p|auth)\\//.test(p)&&!sessionStorage.getItem("${INTRO_KEY}")&&!matchMedia("(prefers-reduced-motion: reduce)").matches){document.documentElement.dataset.intro="play"}}catch(e){}`;
