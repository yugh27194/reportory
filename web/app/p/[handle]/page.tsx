import { FileText, Link2, Mail, Paperclip } from "lucide-react";
import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Brand, TypeIcon } from "@/components/ui";
import { SERVICE_NAME, env } from "@/lib/env";
import { formatPeriod } from "@/lib/text";
import { DETAIL_LABELS, DOC_FORMATS, ITEM_TYPE_LABELS, ITEM_TYPE_ORDER, type DocFormat, type Item, type Metric } from "@/lib/types";

// 공개 프로필에 보일 세부 값(점수·순위·발급기관·학위)
const PUBLIC_DETAILS = ["score", "level", "rank", "issuer", "degree", "major", "venue"];

type PublicProfile = {
  profile: {
    handle: string;
    display_name: string | null;
    display_name_en: string | null;
    headline: string | null;
    email_public: string | null;
    links: { label: string; url: string }[];
    school: string | null;
    major: string | null;
  };
  items: (Item & { skills: string[]; evidence: { id: string; kind: string | null; file_name: string }[] })[];
  documents: { id: string; title: string; format: DocFormat; language: string; version_at: string }[];
  last_updated: string;
};

async function load(handle: string): Promise<PublicProfile | null> {
  // 공개 설정을 바꾸면 바로 보이도록 캐시하지 않는다.
  const res = await fetch(`${env.apiBaseUrl}/public/${encodeURIComponent(handle)}`, { cache: "no-store" });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`public profile ${res.status}`);
  return res.json();
}

export async function generateMetadata({ params }: { params: Promise<{ handle: string }> }): Promise<Metadata> {
  const { handle } = await params;
  const data = await load(handle);
  if (!data) return { title: "프로필을 찾을 수 없다" };
  const name = data.profile.display_name ?? handle;
  const description =
    data.profile.headline || [data.profile.school, data.profile.major].filter(Boolean).join(" ") || `${name}의 포트폴리오`;
  return {
    title: name,
    description,
    openGraph: { title: `${name} · ${SERVICE_NAME}`, description, url: `${env.siteUrl}/p/${handle}`, type: "profile" },
  };
}

const metricText = (m: Metric) => `${m.name} ${m.value}${m.unit ?? ""}`;

export default async function PublicProfilePage({ params }: { params: Promise<{ handle: string }> }) {
  const { handle } = await params;
  const data = await load(handle);
  if (!data) notFound();
  const { profile, items, documents } = data;
  const groups = ITEM_TYPE_ORDER.map((t) => ({ type: t, items: items.filter((i) => i.type === t) })).filter((g) => g.items.length);
  const name = profile.display_name ?? handle;
  const api = env.apiBaseUrl;

  return (
    <main className="min-h-screen bg-paper">
      <div className="h-40 bg-ink bg-[radial-gradient(ellipse_at_75%_20%,rgba(79,209,197,0.30),transparent_55%)]" />
      <div className="mx-auto -mt-20 max-w-3xl px-5 pb-16">
        <header className="card p-7">
          <span className="inline-flex h-20 w-20 items-center justify-center rounded-3xl bg-deep text-3xl font-bold text-mint ring-4 ring-white">
            {name.slice(0, 1)}
          </span>
          <h1 className="mt-4 text-3xl font-bold tracking-tight">{name}</h1>
          {profile.display_name_en && <p className="text-muted">{profile.display_name_en}</p>}
          {profile.headline && <p className="mt-2 text-lg">{profile.headline}</p>}
          {(profile.school || profile.major) && (
            <p className="mt-1 text-sm text-muted">{[profile.school, profile.major].filter(Boolean).join(" · ")}</p>
          )}
          <div className="mt-4 flex flex-wrap gap-2">
            {profile.email_public && (
              <a className="chip chip-cream hover:bg-mint" href={`mailto:${profile.email_public}`}>
                <Mail size={12} /> {profile.email_public}
              </a>
            )}
            {profile.links.map((l) => (
              <a key={l.url} className="chip chip-cream hover:bg-mint" href={l.url} target="_blank" rel="noopener noreferrer">
                <Link2 size={12} /> {l.label}
              </a>
            ))}
          </div>
        </header>

        {documents.length > 0 && (
          <section className="mt-8">
            <h2 className="section-title mb-3">문서</h2>
            <div className="grid gap-3 sm:grid-cols-2">
              {documents.map((d) => (
                <a
                  key={d.id}
                  href={`${api}/public/${handle}/documents/${d.id}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="card card-hover flex items-center gap-3 p-4"
                >
                  <span className="inline-flex h-10 w-10 items-center justify-center rounded-xl bg-ink text-accent">
                    <FileText size={18} />
                  </span>
                  <span className="min-w-0">
                    <span className="block truncate font-semibold">{d.title}</span>
                    <span className="text-xs text-muted">{DOC_FORMATS.find((f) => f.key === d.format)?.label} · PDF</span>
                  </span>
                </a>
              ))}
            </div>
          </section>
        )}

        {groups.length === 0 && <p className="mt-10 text-center text-muted">아직 공개한 항목이 없다.</p>}
        {groups.map((g) => (
          <section key={g.type} className="mt-10">
            <h2 className="section-title mb-4 flex items-center gap-2">
              <TypeIcon type={g.type} size="sm" /> {ITEM_TYPE_LABELS[g.type]}
            </h2>
            <ol className="space-y-6">
              {g.items.map((i) => (
                <li key={i.id} className="grid gap-1 sm:grid-cols-[140px_1fr] sm:gap-6">
                  <p className="pt-0.5 text-sm text-muted">{formatPeriod(i.start_date, i.end_date, i.is_ongoing)}</p>
                  <div>
                    <h3 className="font-semibold">{i.title}</h3>
                    {(i.organization || i.role) && (
                      <p className="text-sm text-muted">{[i.organization, i.role].filter(Boolean).join(" · ")}</p>
                    )}
                    {PUBLIC_DETAILS.some((k) => i.details?.[k]) && (
                      <p className="mt-1 text-sm text-deep">
                        {PUBLIC_DETAILS.filter((k) => i.details?.[k])
                          .map((k) => `${DETAIL_LABELS[k]} ${String(i.details[k])}`)
                          .join(" · ")}
                      </p>
                    )}
                    {i.summary && <p className="mt-2 text-[15px] leading-relaxed text-ink/85">{i.summary}</p>}
                    {(i.metrics.length > 0 || i.skills.length > 0) && (
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        {i.metrics.map((m) => (
                          <span key={m.name} className="chip chip-ink">
                            {metricText(m)}
                          </span>
                        ))}
                        {i.skills.map((s) => (
                          <span key={s} className="chip">
                            {s}
                          </span>
                        ))}
                      </div>
                    )}
                    {i.evidence.length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-3">
                        {i.evidence.map((e) => (
                          <a
                            key={e.id}
                            className="inline-flex items-center gap-1 text-xs text-deep hover:underline"
                            href={`${api}/public/${handle}/evidence/${e.id}`}
                            target="_blank"
                            rel="noopener noreferrer"
                          >
                            <Paperclip size={12} /> 증빙 보기
                          </a>
                        ))}
                      </div>
                    )}
                  </div>
                </li>
              ))}
            </ol>
          </section>
        ))}

        <footer className="mt-16 flex flex-wrap items-center gap-2 border-t border-line pt-5 text-xs text-muted">
          <span>최종 갱신일 {new Date(data.last_updated).toLocaleDateString("ko-KR")}</span>
          <span className="ml-auto">
            <Brand className="text-xs" />로 만든 프로필
          </span>
        </footer>
      </div>
    </main>
  );
}
