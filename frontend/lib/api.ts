import { getAccessToken } from "./supabase";

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public code: string,
    public requestId?: string,
  ) {
    super(message);
  }
}

type Options = { method?: string; body?: unknown; signal?: AbortSignal; form?: FormData };

export async function api<T>(path: string, opts: Options = {}): Promise<T> {
  const headers: Record<string, string> = {};
  const token = await getAccessToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  let body: BodyInit | undefined;
  if (opts.form) body = opts.form;
  else if (opts.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opts.body);
  }
  let res: Response;
  try {
    res = await fetch(`/api/v1${path}`, {
      method: opts.method ?? (body ? "POST" : "GET"),
      headers,
      body,
      credentials: "include",
      signal: opts.signal,
    });
  } catch (e) {
    if ((e as Error).name === "AbortError") throw e;
    throw new ApiError("Can't reach the server. Check your connection and try again.", 0, "network");
  }
  if (res.status === 204) return undefined as T;
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    const err = data?.error;
    throw new ApiError(
      err?.message ?? `Request failed (${res.status})`,
      res.status,
      err?.code ?? "error",
      err?.request_id ?? res.headers.get("x-request-id") ?? undefined,
    );
  }
  return data as T;
}

export function errorMessage(e: unknown): string {
  if (e instanceof ApiError) return e.message;
  return "Something went wrong. Please try again.";
}
