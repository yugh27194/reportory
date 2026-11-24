import type { Metadata } from "next";
import { SERVICE_NAME, env } from "@/lib/env";
import { Providers } from "./providers";
import "pretendard/dist/web/variable/pretendardvariable-dynamic-subset.css";
import "./globals.css";

export const metadata: Metadata = {
  metadataBase: new URL(env.siteUrl),
  title: { default: SERVICE_NAME, template: `%s · ${SERVICE_NAME}` },
  description: "일기처럼 쓴 기록이 포트폴리오가 되는 서비스다.",
  icons: { icon: "/favicon.svg" },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
