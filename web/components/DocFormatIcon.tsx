import { BookMarked, FileText, Globe2, Presentation } from "lucide-react";
import type { DocFormat } from "@/lib/types";

const ICONS = { resume_ko: FileText, resume_en: Globe2, academic_cv: BookMarked, project_portfolio: Presentation };
const TONES = {
  resume_ko: "bg-mint text-deep",
  resume_en: "bg-accent/25 text-deep",
  academic_cv: "bg-deep text-mint",
  project_portfolio: "bg-ink text-accent",
};

export function DocFormatIcon({ format, size = 20 }: { format: DocFormat; size?: number }) {
  const Icon = ICONS[format];
  return (
    <span className={`inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl ${TONES[format]}`}>
      <Icon size={size} />
    </span>
  );
}
