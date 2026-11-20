"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { SERVICE_NAME } from "@/lib/env";
import { supabaseBrowser } from "@/lib/supabase/client";

const LINKS = [
  { href: "/journal", label: "일기" },
  { href: "/review", label: "검토" },
  { href: "/portfolio", label: "포트폴리오" },
  { href: "/settings", label: "설정" },
];

export function usePendingCount() {
  return useQuery({
    queryKey: ["pending-count"],
    queryFn: () => api<{ proposals: number; followups: number }>("/proposals/count"),
    refetchInterval: 30_000,
  });
}

export function AppNav() {
  const path = usePathname();
  const router = useRouter();
  const { data } = usePendingCount();
  const pending = (data?.proposals ?? 0) + (data?.followups ?? 0);

  async function logout() {
    await supabaseBrowser().auth.signOut();
    router.replace("/login");
  }

  return (
    <header className="border-b border-zinc-200 bg-white">
      <nav className="mx-auto flex max-w-5xl items-center gap-1 px-4 py-2">
        <Link href="/journal" className="mr-4 font-semibold text-brand">
          {SERVICE_NAME}
        </Link>
        {LINKS.map((l) => (
          <Link
            key={l.href}
            href={l.href}
            className={`relative rounded-md px-3 py-1.5 text-sm ${
              path.startsWith(l.href) ? "bg-brand-soft font-medium text-brand" : "text-zinc-600 hover:bg-zinc-100"
            }`}
          >
            {l.label}
            {l.href === "/review" && pending > 0 && (
              <span
                aria-label={`검토 대기 ${pending}건`}
                className="ml-1 rounded-full bg-brand px-1.5 text-xs text-white"
              >
                {pending}
              </span>
            )}
          </Link>
        ))}
        <button onClick={logout} className="ml-auto text-sm text-zinc-500 hover:text-zinc-800">
          로그아웃
        </button>
      </nav>
    </header>
  );
}
