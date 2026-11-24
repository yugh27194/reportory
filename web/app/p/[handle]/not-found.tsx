import Link from "next/link";
import { Brand } from "@/components/ui";

export default function NotFound() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-paper px-6 text-center">
      <Brand className="text-xl" />
      <h1 className="mt-8 text-2xl font-bold">공개 프로필을 찾을 수 없다.</h1>
      <p className="mt-2 text-sm text-muted">주소가 바뀌었거나 공개를 끈 프로필이다.</p>
      <Link href="/" className="btn mt-6">
        처음으로
      </Link>
    </main>
  );
}
