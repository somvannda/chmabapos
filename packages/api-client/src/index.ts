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
  /** Called on a 401 response before the error is thrown (e.g. to sign the user out). */
  onUnauthorized?: (status: number, token: string | null | undefined) => void;
  /**
   * Called for every failed request (a non-2xx response, or a fetch that never
   * produced one). The raw path and body are handed over so the caller can
   * reduce them to a value-free key; nothing here reaches the network.
   */
  onRequestError?: (failure: RequestFailure) => void;
  /** Build the error message from the response body. Defaults to the detail string. */
  formatError?: (body: unknown, status: number) => string;
};

export type RequestFailure = {
  /** Uppercased HTTP verb, or "GET" when the caller used the default. */
  method: string;
  /** The path as requested (may carry a query string); mask before sending. */
  path: string;
  /** 0 for a request that never got a response. */
  status: number;
  /** Parsed response body, or null for a network failure. */
  body: unknown;
  /** True when fetch itself threw (offline, DNS, aborted). */
  network: boolean;
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
    this.name = "APIError";
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

  // Telemetry is observability: a broken reporter must never fail the request
  // it is describing, so the callback is isolated from the request path.
  function reportFailure(failure: RequestFailure) {
    try {
      options.onRequestError?.(failure);
    } catch {
      /* ignore */
    }
  }

  async function request<T>(path: string, init: RequestOptions = {}): Promise<T> {
    const { token: tokenOverride, storeId: storeIdOverride, ...rest } = init;
    const method = String(rest.method || "GET").toUpperCase();
    const headers = new Headers(rest.headers);
    if (rest.body && !(rest.body instanceof FormData) && !headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }
    const token = tokenOverride ?? options.getToken?.();
    if (token) headers.set("Authorization", `Bearer ${token}`);
    const storeId = storeIdOverride ?? options.getStoreId?.();
    if (storeId) headers.set("X-Store-ID", storeId);
    let response: Response;
    try {
      response = await doFetch(`${baseUrl}${path}`, { ...rest, headers, credentials: "include" });
    } catch (error) {
      reportFailure({ method, path, status: 0, body: null, network: true });
      throw error;
    }
    const contentType = response.headers.get("content-type") || "";
    const body = contentType.includes("application/json") ? await response.json() : await response.text();
    if (!response.ok) {
      if (response.status === 401) options.onUnauthorized?.(response.status, token);
      reportFailure({ method, path, status: response.status, body, network: false });
      const message = options.formatError ? options.formatError(body, response.status) : formatDetail(body, response.status);
      throw new ApiError(message, response.status, body);
    }
    return body as T;
  }

  return { baseUrl, request };
}

export type ApiClient = ReturnType<typeof createApiClient>;
