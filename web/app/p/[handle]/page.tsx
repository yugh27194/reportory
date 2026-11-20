import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { SERVICE_NAME, env } from "@/lib/env";
import { formatPeriod } from "@/lib/text";
import { ITEM_TYPE_LABELS, ITEM_TYPE_ORDER, type Item } from "@/lib/types";

type PublicProfile = {
  profile: {
    handle: string;
    display_name: string | null;
    display_name_en: string | null;
    email_public: string | null;
    links: { label: string; url: string }[];
    school: string | null;
    major: string | null;
  };
  items: (Item & { skills: string[] })[];
  last_updated: string;
};

async function load(handle: string): Promise<PublicProfile | null> {
  const res = await fetch(`${env.apiBaseUrl}/public/${encodeURIComponent(handle)}`, {
    next: { revalidate: 60 },
  });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`public profile ${res.status}`);
  return res.json();
}

export async function generateMetadata({ params }: { params: Promise<{ handle: string }> }): Promise<Metadata> {
  const { handle } = await params;
  const data = await load(handle);
  if (!data) return { title: "프로필을 찾을 수 없다" };
  const name = data.profile.display_name ?? handle;
  const description = [data.profile.school, data.profile.major].filter(Boolean).join(" ") || `${name}의 포트폴리오`;
  return {
    title: name,
    description,
    openGraph: {
      title: `${name} · ${SERVICE_NAME}`,
      description,
      url: `${env.siteUrl}/p/${handle}`,
      type: "profile",
    },
  };
}

export default async function PublicProfilePage({ params }: { params: Promise<{ handle: string }> }) {
  const { handle } = await params;
  const data = await load(handle);
  if (!data) notFound();
  const { profile, items } = data;
  const groups = ITEM_TYPE_ORDER.map((t) => ({ type: t, items: items.filter((i) => i.type === t) })).filter(
    (g) => g.items.length > 0,
  );

  return (
    <main className="mx-auto max-w-3xl space-y-8 px-6 py-12">
      <header className="space-y-1">
        <h1 className="text-3xl font-bold">{profile.display_name ?? handle}</h1>
        {profile.display_name_en && <p className="text-zinc-500">{profile.display_name_en}</p>}
        <p className="text-zinc-600">{[profile.school, profile.major].filter(Boolean).join(" · ")}</p>
        <div className="flex flex-wrap gap-3 pt-2 text-sm">
          {profile.email_public && (
            <a className="text-brand underline" href={`mailto:${profile.email_public}`}>
              {profile.email_public}
            </a>
          )}
          {profile.links.map((l) => (
            <a key={l.url} className="text-brand underline" href={l.url} rel="noopener noreferrer" target="_blank">
              {l.label}
            </a>
          ))}
        </div>
      </header>
      {groups.length === 0 && <p className="text-zinc-500">아직 공개한 항목이 없다.</p>}
      {groups.map((g) => (
        <section key={g.type} className="space-y-3">
          <h2 className="border-b border-zinc-200 pb-1 text-sm font-semibold uppercase tracking-wide text-zinc-500">
            {ITEM_TYPE_LABELS[g.type]}
          </h2>
          {g.items.map((i) => (
            <article key={i.id} className="space-y-1">
              <div className="flex flex-wrap items-baseline gap-x-3">
                <h3 className="font-semibold">{i.title}</h3>
                <span className="text-sm text-zinc-500">
                  {[i.organization, i.role, formatPeriod(i.start_date, i.end_date, i.is_ongoing)]
                    .filter(Boolean)
                    .join(" · ")}
                </span>
              </div>
              {i.summary && <p className="text-sm leading-relaxed text-zinc-700">{i.summary}</p>}
              {i.skills.length > 0 && <p className="text-xs text-zinc-500">{i.skills.join(" · ")}</p>}
            </article>
          ))}
        </section>
      ))}
      <footer className="border-t border-zinc-200 pt-4 text-xs text-zinc-400">
        최종 갱신일 {new Date(data.last_updated).toLocaleDateString("ko-KR")} · {SERVICE_NAME}
      </footer>
    </main>
  );
}
