"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Bell,
  CheckCheck,
  ClipboardCheck,
  ExternalLink,
  FileText,
  Home,
  LayoutGrid,
  LogOut,
  Menu,
  NotebookPen,
  Settings,
  Sparkles,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { Brand } from "@/components/ui";
import { api, post } from "@/lib/api";
import { supabaseBrowser } from "@/lib/supabase/client";
import type { Notification, Profile } from "@/lib/types";

const NAV = [
  { href: "/dashboard", label: "홈", icon: Home },
  { href: "/journal", label: "일기", icon: NotebookPen },
  { href: "/review", label: "검토", icon: ClipboardCheck, badge: true },
  { href: "/portfolio", label: "포트폴리오", icon: LayoutGrid },
  { href: "/documents", label: "문서", icon: FileText },
  { href: "/summaries", label: "요약", icon: Sparkles },
  { href: "/settings", label: "설정", icon: Settings },
];

export function usePendingCount() {
  return useQuery({
    queryKey: ["pending-count"],
    queryFn: () => api<{ proposals: number; followups: number }>("/proposals/count"),
    refetchInterval: 30_000,
  });
}

export function useMe() {
  return useQuery({ queryKey: ["me"], queryFn: () => api<{ user_id: string; profile: Profile }>("/me") });
}

function timeAgo(iso: string) {
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60) return "방금";
  if (diff < 3600) return `${Math.floor(diff / 60)}분 전`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}시간 전`;
  return `${Math.floor(diff / 86400)}일 전`;
}

function NotificationBell() {
  const qc = useQueryClient();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const { data } = useQuery({
    queryKey: ["notifications"],
    queryFn: () => api<{ notifications: Notification[]; unread: number }>("/notifications"),
    refetchInterval: 30_000,
  });
  const readAll = useMutation({
    mutationFn: (ids?: string[]) => post("/notifications/read", { ids: ids ?? null }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["notifications"] }),
  });
  useEffect(() => {
    const close = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);
  const unread = data?.unread ?? 0;

  return (
    <div className="relative" ref={ref}>
      <button
        className="relative inline-flex h-9 w-9 items-center justify-center rounded-xl text-ink hover:bg-ink/5"
        onClick={() => setOpen((v) => !v)}
        aria-label={`알림 ${unread}건`}
      >
        <Bell size={18} />
        {unread > 0 && (
          <span className="absolute -top-0.5 -right-0.5 min-w-4 rounded-full bg-accent px-1 text-[10px] leading-4 font-bold text-ink">
            {unread > 9 ? "9+" : unread}
          </span>
        )}
      </button>
      {open && (
        <div className="absolute right-0 z-40 mt-2 w-80 overflow-hidden rounded-2xl border border-line bg-white shadow-lift">
          <div className="flex items-center justify-between border-b border-line px-4 py-3">
            <p className="text-sm font-semibold">알림</p>
            {unread > 0 && (
              <button className="inline-flex items-center gap-1 text-xs text-deep" onClick={() => readAll.mutate(undefined)}>
                <CheckCheck size={14} /> 모두 읽음
              </button>
            )}
          </div>
          <ul className="max-h-96 overflow-y-auto">
            {(data?.notifications ?? []).length === 0 && (
              <li className="px-4 py-8 text-center text-sm text-muted">새 알림이 없다.</li>
            )}
            {data?.notifications.map((n) => (
              <li key={n.id}>
                <button
                  className={`flex w-full gap-3 px-4 py-3 text-left text-sm hover:bg-cream/60 ${n.read_at ? "text-muted" : ""}`}
                  onClick={() => {
                    if (!n.read_at) readAll.mutate([n.id]);
                    setOpen(false);
                    if (n.link) router.push(n.link);
                  }}
                >
                  <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${n.read_at ? "bg-transparent" : "bg-accent"}`} />
                  <span className="min-w-0">
                    <span className="block">{n.title}</span>
                    <span className="text-xs text-muted">{timeAgo(n.created_at)}</span>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function NavLinks({ onNavigate }: { onNavigate?: () => void }) {
  const path = usePathname();
  const { data } = usePendingCount();
  const pending = (data?.proposals ?? 0) + (data?.followups ?? 0);
  return (
    <nav className="space-y-0.5">
      {NAV.map(({ href, label, icon: Icon, badge }) => {
        const active = path === href || path.startsWith(`${href}/`);
        return (
          <Link
            key={href}
            href={href}
            onClick={onNavigate}
            className={`group flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition ${
              active ? "bg-white/10 text-white" : "text-white/60 hover:bg-white/5 hover:text-white"
            }`}
          >
            <Icon size={18} className={active ? "text-accent" : "text-white/50 group-hover:text-accent"} />
            {label}
            {badge && pending > 0 && (
              <span aria-label={`검토 대기 ${pending}건`} className="ml-auto rounded-full bg-accent px-2 text-xs font-bold text-ink">
                {pending}
              </span>
            )}
          </Link>
        );
      })}
    </nav>
  );
}

function SidebarBody({ onNavigate }: { onNavigate?: () => void }) {
  const router = useRouter();
  const { data } = useMe();
  const p = data?.profile;
  async function logout() {
    await supabaseBrowser().auth.signOut();
    router.replace("/login");
  }
  return (
    <div className="flex h-full flex-col gap-6 p-4">
      <Link href="/dashboard" className="px-2 pt-2 text-xl" onClick={onNavigate}>
        <Brand dark />
      </Link>
      <Link href="/journal" onClick={onNavigate} className="btn btn-accent w-full justify-start">
        <NotebookPen size={16} /> 오늘 일기 쓰기
      </Link>
      <NavLinks onNavigate={onNavigate} />
      <div className="mt-auto space-y-2 border-t border-white/10 pt-4">
        {p?.public_profile_enabled && p.handle && (
          <Link
            href={`/p/${p.handle}`}
            target="_blank"
            className="flex items-center gap-2 rounded-xl px-3 py-2 text-xs text-white/60 hover:text-accent"
          >
            <ExternalLink size={14} /> 내 공개 프로필 보기
          </Link>
        )}
        <div className="flex items-center gap-3 px-3">
          <span className="inline-flex h-8 w-8 items-center justify-center rounded-full bg-deep text-sm font-bold text-mint">
            {(p?.display_name ?? "나").slice(0, 1)}
          </span>
          <span className="min-w-0 flex-1 truncate text-sm text-white/80">{p?.display_name ?? "이름을 정해 보세요"}</span>
          <button onClick={logout} className="text-white/50 hover:text-white" aria-label="로그아웃" title="로그아웃">
            <LogOut size={16} />
          </button>
        </div>
      </div>
    </div>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const [drawer, setDrawer] = useState(false);
  return (
    <div className="min-h-screen lg:pl-64">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 bg-ink lg:block">
        <SidebarBody />
      </aside>
      {drawer && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-ink/50" onClick={() => setDrawer(false)} />
          <aside className="absolute inset-y-0 left-0 w-72 bg-ink">
            <button
              className="absolute top-4 right-3 text-white/60"
              onClick={() => setDrawer(false)}
              aria-label="메뉴 닫기"
            >
              <X size={20} />
            </button>
            <SidebarBody onNavigate={() => setDrawer(false)} />
          </aside>
        </div>
      )}
      <header className="sticky top-0 z-20 flex h-14 items-center gap-2 border-b border-line/70 bg-paper/85 px-4 backdrop-blur lg:px-8">
        <button className="btn-ghost -ml-1 rounded-lg p-2 lg:hidden" onClick={() => setDrawer(true)} aria-label="메뉴 열기">
          <Menu size={20} />
        </button>
        <Link href="/dashboard" className="text-lg lg:hidden">
          <Brand />
        </Link>
        <div className="ml-auto">
          <NotificationBell />
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-8 lg:px-8">{children}</main>
    </div>
  );
}
