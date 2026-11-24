"use client";

import { env } from "@/lib/env";
import { supabaseBrowser } from "@/lib/supabase/client";

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
  }
}

/** FastAPI 호출 래퍼. Supabase access token을 Bearer로 붙이고, 오류 형식을 ApiError로 바꾼다. */
export async function api<T = unknown>(path: string, init: RequestInit = {}): Promise<T> {
  const {
    data: { session },
  } = await supabaseBrowser().auth.getSession();
  const headers = new Headers(init.headers);
  if (session) headers.set("Authorization", `Bearer ${session.access_token}`);
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");

  const res = await fetch(`${env.apiBaseUrl}${path}`, { ...init, headers });
  if (res.status === 204) return undefined as T;
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const err = body?.error ?? {};
    throw new ApiError(res.status, err.code ?? "error", err.message ?? "요청을 처리하지 못했다.");
  }
  return body as T;
}

export const post = <T = unknown>(path: string, data?: unknown) =>
  api<T>(path, { method: "POST", body: data === undefined ? undefined : JSON.stringify(data) });

export const patch = <T = unknown>(path: string, data: unknown) =>
  api<T>(path, { method: "PATCH", body: JSON.stringify(data) });

export const put = <T = unknown>(path: string, data: unknown) =>
  api<T>(path, { method: "PUT", body: JSON.stringify(data) });

/** 파일 업로드(multipart). Content-Type은 브라우저가 정한다. */
export const upload = <T = unknown>(path: string, file: File, fields: Record<string, string> = {}) => {
  const form = new FormData();
  form.append("file", file);
  Object.entries(fields).forEach(([k, v]) => form.append(k, v));
  return api<T>(path, { method: "POST", body: form });
};

export const del = <T = unknown>(path: string, data?: unknown) =>
  api<T>(path, { method: "DELETE", body: data === undefined ? undefined : JSON.stringify(data) });
