import {
  Award,
  BadgeCheck,
  BookOpen,
  Briefcase,
  FolderGit2,
  GraduationCap,
  Languages,
  Loader2,
  Users,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import { LogoMark } from "@/components/Logo";
import type { ItemType } from "@/lib/types";

/** 서비스 표기: :P 로고 + re:portory(콜론은 강조색). */
export function Brand({
  className = "",
  dark = false,
  mark = true,
}: {
  className?: string;
  dark?: boolean;
  mark?: boolean;
}) {
  return (
    <span className={`inline-flex items-center gap-2 font-bold tracking-tight ${dark ? "text-white" : "text-ink"} ${className}`}>
      {mark && <LogoMark size={28} className={dark ? "ring-1 ring-white/15 rounded-[8px]" : ""} />}
      <span>
        re<span className="text-accent">:</span>portory
      </span>
    </span>
  );
}

export const TYPE_ICONS: Record<ItemType, LucideIcon> = {
  education: GraduationCap,
  experience: Briefcase,
  project: FolderGit2,
  activity: Users,
  award: Award,
  certification: BadgeCheck,
  language_test: Languages,
  publication: BookOpen,
};

const TYPE_TONES: Record<ItemType, string> = {
  education: "bg-mint text-deep",
  experience: "bg-deep text-mint",
  project: "bg-accent/25 text-deep",
  activity: "bg-cream text-deep ring-1 ring-line",
  award: "bg-ink text-accent",
  certification: "bg-mint text-ink",
  language_test: "bg-accent/15 text-ink",
  publication: "bg-cream text-ink ring-1 ring-line",
};

export function TypeIcon({ type, size = "md" }: { type: ItemType; size?: "sm" | "md" | "lg" }) {
  const Icon = TYPE_ICONS[type];
  const box = { sm: "h-7 w-7 rounded-lg", md: "h-9 w-9 rounded-xl", lg: "h-12 w-12 rounded-2xl" }[size];
  const icon = { sm: 14, md: 18, lg: 24 }[size];
  return (
    <span className={`inline-flex shrink-0 items-center justify-center ${box} ${TYPE_TONES[type]}`}>
      <Icon size={icon} strokeWidth={2} aria-hidden />
    </span>
  );
}

export function PageHeader({
  title,
  description,
  actions,
  eyebrow,
}: {
  title: string;
  description?: React.ReactNode;
  actions?: React.ReactNode;
  eyebrow?: string;
}) {
  return (
    <div className="mb-6 flex flex-wrap items-end gap-4">
      <div className="mr-auto min-w-0">
        {eyebrow && <p className="section-title mb-1">{eyebrow}</p>}
        <h1 className="page-title">{title}</h1>
        {description && <p className="mt-1 text-sm text-muted">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
}: {
  icon: LucideIcon;
  title: string;
  description?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center rounded-2xl border border-dashed border-line bg-white/60 px-6 py-12 text-center">
      <span className="mb-3 inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-mint text-deep">
        <Icon size={22} aria-hidden />
      </span>
      <p className="font-semibold">{title}</p>
      {description && <p className="mt-1 max-w-sm text-sm text-muted">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function StatCard({
  label,
  value,
  hint,
  href,
  tone = "white",
}: {
  label: string;
  value: React.ReactNode;
  hint?: string;
  href?: string;
  tone?: "white" | "ink" | "mint";
}) {
  const tones = {
    white: "bg-white border-line/80 text-ink",
    ink: "bg-ink border-ink text-white",
    mint: "bg-mint border-accent/30 text-ink",
  };
  const body = (
    <div className={`h-full rounded-2xl border p-4 shadow-card sm:p-5 ${tones[tone]} ${href ? "card-hover" : ""}`}>
      <p className={`text-xs font-semibold ${tone === "ink" ? "text-accent" : "text-muted"}`}>{label}</p>
      <p className="mt-2 text-2xl font-bold tracking-tight sm:text-3xl">{value}</p>
      {hint && <p className={`mt-1 text-xs ${tone === "ink" ? "text-white/60" : "text-muted"}`}>{hint}</p>}
    </div>
  );
  return href ? <Link href={href}>{body}</Link> : body;
}

export function Spinner({ label }: { label?: string }) {
  return (
    <span className="inline-flex items-center gap-2 text-sm text-muted">
      <Loader2 size={16} className="animate-spin text-accent-2" aria-hidden />
      {label}
    </span>
  );
}

export function Tabs<T extends string>({
  value,
  onChange,
  tabs,
}: {
  value: T;
  onChange: (v: T) => void;
  tabs: { key: T; label: React.ReactNode }[];
}) {
  return (
    <div className="inline-flex rounded-xl bg-ink/5 p-1" role="tablist">
      {tabs.map((t) => (
        <button
          key={t.key}
          role="tab"
          aria-selected={value === t.key}
          onClick={() => onChange(t.key)}
          className={`rounded-lg px-4 py-1.5 text-sm font-medium transition ${
            value === t.key ? "bg-white text-ink shadow-card" : "text-muted hover:text-ink"
          }`}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}

/** 요약용 아주 작은 마크다운: "- " 목록과 문단만 다룬다(HTML을 그대로 넣지 않는다). */
export function MarkdownLite({ text }: { text: string }) {
  const blocks: React.ReactNode[] = [];
  let list: string[] = [];
  const flush = () => {
    if (list.length) {
      blocks.push(
        <ul key={`l${blocks.length}`} className="ml-4 list-disc space-y-1 marker:text-accent-2">
          {list.map((l, i) => (
            <li key={i}>{l}</li>
          ))}
        </ul>,
      );
      list = [];
    }
  };
  text.split("\n").forEach((raw) => {
    const line = raw.trim();
    if (!line) return flush();
    if (/^[-*] /.test(line)) list.push(line.slice(2));
    else {
      flush();
      blocks.push(<p key={`p${blocks.length}`}>{line.replace(/^#+\s*/, "")}</p>);
    }
  });
  flush();
  return <div className="space-y-2 text-sm leading-relaxed">{blocks}</div>;
}

export function StatusDot({ status }: { status: "queued" | "running" | "succeeded" | "failed" | string }) {
  const map: Record<string, [string, string]> = {
    queued: ["bg-amber-400", "대기"],
    running: ["bg-accent animate-pulse", "진행 중"],
    succeeded: ["bg-deep", "완료"],
    failed: ["bg-red-500", "실패"],
  };
  const [cls, label] = map[status] ?? ["bg-muted", status];
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-muted">
      <span className={`h-2 w-2 rounded-full ${cls}`} />
      {label}
    </span>
  );
}
