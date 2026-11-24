import { NextResponse, type NextRequest } from "next/server";
import { supabaseServer } from "@/lib/supabase/server";

// 매직링크·GitHub 로그인 뒤 돌아오는 주소다. code를 세션으로 바꾼다.
export async function GET(request: NextRequest) {
  const url = new URL(request.url);
  const code = url.searchParams.get("code");
  const next = url.searchParams.get("next") ?? "/dashboard";
  const safeNext = next.startsWith("/") && !next.startsWith("//") ? next : "/dashboard";
  if (code) {
    const supabase = await supabaseServer();
    const { error } = await supabase.auth.exchangeCodeForSession(code);
    if (!error) return NextResponse.redirect(new URL(safeNext, url.origin));
  }
  const fail = new URL("/login", url.origin);
  fail.searchParams.set("error", "로그인을 마치지 못했다. 다시 시도해 보세요.");
  return NextResponse.redirect(fail);
}
