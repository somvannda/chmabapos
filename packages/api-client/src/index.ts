// Chmaba API client (ADR-005).
//
// `src/schema.d.ts` is generated from `chmabapos_api/openapi.json` by
// `npm run generate`; never edit it by hand. This module ships the generated
// types plus a thin typed fetch wrapper both apps can adopt incrementally
// (replacing the hand-rolled `apps/*/src/api.js`).

export type { paths, components, operations } from "./schema";

export type ApiClientOptions = {
  baseUrl: string;
  /** Bearer token for the current session, or null/undefined when signed out. */
  getToken?: () => string | null | undefined;
  /** Active store id, sent as X-Store-ID on tenant requests. */
  getStoreId?: () => string | null | undefined;
  /** Injectable fetch (tests / non-browser runtimes). Defaults to global fetch. */
  fetchImpl?: typeof fetch;
};

export type RequestOptions = RequestInit & {
  /** Per-call bearer token; overrides the factory's getToken. */
  token?: string | null;
  /** Per-call store id; overrides the factory's getStoreId. */
  storeId?: string | null;
};

export class ApiError extends Error {
  status: number;
  body: unknown;

  constructor(message: string, status: number, body: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

function formatDetail(body: unknown, status: number): string {
  if (body && typeof body === "object" && "detail" in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    return JSON.stringify(detail);
  }
  return `Request failed (${status})`;
}

export function createApiClient(options: ApiClientOptions) {
  const doFetch = options.fetchImpl ?? fetch;
  const baseUrl = options.baseUrl.replace(/\/$/, "");

  async function request<T>(path: string, init: RequestOptions = {}): Promise<T> {
    const { token: tokenOverride, storeId: storeIdOverride, ...rest } = init;
    const headers = new Headers(rest.headers);
    if (rest.body && !(rest.body instanceof FormData) && !headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }
    const token = tokenOverride ?? options.getToken?.();
    if (token) headers.set("Authorization", `Bearer ${token}`);
    const storeId = storeIdOverride ?? options.getStoreId?.();
    if (storeId) headers.set("X-Store-ID", storeId);
    const response = await doFetch(`${baseUrl}${path}`, { ...rest, headers, credentials: "include" });
    const contentType = response.headers.get("content-type") || "";
    const body = contentType.includes("application/json") ? await response.json() : await response.text();
    if (!response.ok) throw new ApiError(formatDetail(body, response.status), response.status, body);
    return body as T;
  }

  return { baseUrl, request };
}

export type ApiClient = ReturnType<typeof createApiClient>;
