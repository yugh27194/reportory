import { ApiError } from "@/lib/api";

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  return "요청을 처리하지 못했다. 잠시 뒤 다시 시도해 보세요.";
}

export function ErrorText({ error }: { error: unknown }) {
  if (!error) return null;
  return <p className="text-sm text-red-700">{errorMessage(error)}</p>;
}
