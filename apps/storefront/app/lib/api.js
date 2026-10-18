// API access for the storefront.
//
// Two bases, because there are two callers:
//   - the browser calls the storefront host's own /api path, which the edge
//     proxies to the API container, keeping requests same-origin;
//   - the server-side render calls the API container directly over the private
//     network, so a page can be rendered without a round trip through the
//     public origin.

const PUBLIC_BASE = (import.meta.env.VITE_API_URL || "/api/v1").replace(/\/+$/, "");

function base() {
  if (typeof window !== "undefined") return PUBLIC_BASE;
  // globalThis.process is absent in the browser, so this is server-only in
  // practice while still being safe to evaluate anywhere.
  const internal = globalThis.process?.env?.INTERNAL_API_URL;
  return (internal || PUBLIC_BASE).replace(/\/+$/, "");
}

async function get(path, token) {
  const headers = { Accept: "application/json" };
  if (token) headers.Authorization = `Bearer ${token}`;
  const response = await fetch(`${base()}${path}`, { headers });
  if (response.status === 404) return null;
  if (!response.ok) throw new Response("Upstream request failed", { status: response.status });
  return response.json();
}

async function post(path, body, token) {
  const response = await fetch(`${base()}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    // Surface the API's own message so the shopper reads "Insufficient stock for
    // Counter Latte" rather than a generic failure.
    let detail = "Could not place the order";
    try {
      const data = await response.json();
      if (data && data.detail) detail = data.detail;
    } catch { /* keep the default */ }
    throw new Response(detail, { status: response.status });
  }
  return response.json();
}

// The public payload for a store, addressed by its slugs. `null` means the
// address does not resolve to a published, active store.
export function fetchStore(companySlug, storeSlug) {
  return get(`/public/store/${encodeURIComponent(companySlug)}/${encodeURIComponent(storeSlug)}`);
}

// The public directory. Paged server-side, so the page never asks for every store.
export async function fetchDirectory({ q = "", vertical = "", limit = 24, offset = 0 } = {}) {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  if (q.trim()) params.set("q", q.trim());
  if (vertical.trim()) params.set("vertical", vertical.trim());
  // Always answer with the shape this function promises. `get` returns null for a 404 - an
  // unpublished store, a slug that has moved, or a base URL that is simply wrong - and the
  // page destructures `stores` straight into `.length`. A directory that cannot be reached
  // should render as an empty directory, not crash the whole page.
  //
  // The catch is for the other way this fails: an API that is not answering at all rejects the
  // fetch, and an uncaught rejection in a loader takes the page down with a stack trace instead
  // of an empty list.
  let page = null;
  try {
    page = await get(`/public/stores?${params.toString()}`);
  } catch {
    page = null;
  }
  return {
    stores: Array.isArray(page?.stores) ? page.stores : [],
    total: Number(page?.total) || 0,
    verticals: Array.isArray(page?.verticals) ? page.verticals : [],
  };
}

// The directory's own facet: the business types that actually have a listed store.
// This feeds the header's Categories menu, so every entry in it leads to a result, and a
// new business type appears there without a front-end change.
//
// The chrome renders on every page, so the answer is cached briefly: without it every
// navigation would make the render wait on an API round trip it does not need.
const CATEGORY_TTL_MS = 5 * 60 * 1000;
let categoryCache = { at: 0, values: [] };

export async function fetchCategories() {
  if (Date.now() - categoryCache.at < CATEGORY_TTL_MS) return categoryCache.values;
  // The facet rides along with the directory response, so one narrow page is enough.
  const page = await fetchDirectory({ limit: 1 });
  const values = Array.isArray(page?.verticals) ? page.verticals : [];
  categoryCache = { at: Date.now(), values };
  return values;
}

// Place an order against the storefront address. Prices are never sent: the API
// prices every line from the catalogue.
export function submitStoreOrder(companySlug, storeSlug, payload) {
  return post(`/public/store/${encodeURIComponent(companySlug)}/${encodeURIComponent(storeSlug)}/orders`, payload);
}

// Poll a pending storefront payment. Addressed by the order's own token, which is the value
// the confirmation already holds: the shopper is asking about the sale, so the answer comes
// from the sale rather than from the ticket sitting beside it.
export function fetchOrderPayment(orderToken) {
  return get(`/public/order/${encodeURIComponent(orderToken)}/payment`);
}

// An order's status, addressed by its unguessable token. The token is the whole
// authorisation, so this returns only what the customer who owns it may see.
export function fetchOrderStatus(token) {
  return get(`/public/orders/${encodeURIComponent(token)}`);
}

// Shopper accounts. Sign-in is passwordless - a six-digit code by email - so
// there is no password to store anywhere. The token is kept by the caller, not in
// this module, so the API layer stays free of browser storage.
export function requestShopperCode(email) {
  return post("/public/auth/email-code", { email });
}

export function verifyShopperCode(email, code) {
  return post("/public/auth/verify", { email, code });
}

export function fetchShopperMe(token) {
  return get("/public/auth/me", token);
}

export function fetchMyOrders(token) {
  return get("/public/auth/orders", token);
}

// Google and Telegram hand back a *proof* rather than a code: an ID token signed
// by Google, or a payload signed by Telegram. The API verifies both, so nothing
// here is trusted - these only forward what the provider gave the browser.
export function googleShopperSignIn(idToken) {
  return post("/public/auth/google", { id_token: idToken });
}

export function telegramShopperSignIn(payload) {
  return post("/public/auth/telegram", payload);
}

// Money is stored and charged in the store's own currency; render it in that
// currency rather than assuming USD, since shoppers here read both USD and KHR.
export function formatMoney(amount, currencyCode) {
  const value = Number(amount ?? 0);
  try {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: currencyCode || "USD",
      currencyDisplay: "narrowSymbol",
    }).format(value);
  } catch {
    return `${value.toFixed(2)} ${currencyCode || ""}`.trim();
  }
}

// --- Storefront chat -------------------------------------------------------
//
// The same endpoints serve a guest (who proves ownership with an unguessable
// X-Chat-Token kept in the browser) and a signed-in shopper (whose bearer token
// identifies them). Passing both is normal and is what lets a guest keep the
// thread they started once they sign in.

function chatHeaders({ token, chatToken } = {}) {
  const headers = { Accept: "application/json" };
  if (token) headers.Authorization = `Bearer ${token}`;
  if (chatToken) headers["X-Chat-Token"] = chatToken;
  return headers;
}

async function chatRequest(path, { method = "GET", token, chatToken, body, form } = {}) {
  const headers = chatHeaders({ token, chatToken });
  const init = { method, headers };
  if (form) {
    init.body = form;
  } else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(body);
  }
  const response = await fetch(`${base()}${path}`, init);
  if (response.status === 404) return null;
  if (!response.ok) {
    let detail = "Chat request failed";
    try {
      const data = await response.json();
      if (data && data.detail) detail = data.detail;
    } catch { /* keep the default */ }
    throw new Response(detail, { status: response.status });
  }
  if (response.status === 204) return null;
  return response.json();
}

function chatPath(companySlug, storeSlug) {
  return `/public/store/${encodeURIComponent(companySlug)}/${encodeURIComponent(storeSlug)}/chat`;
}

export function fetchChatSession(companySlug, storeSlug, options = {}) {
  return chatRequest(`${chatPath(companySlug, storeSlug)}/session`, options);
}

export function fetchChatMessages(companySlug, storeSlug, { afterSeq = 0, ...options } = {}) {
  return chatRequest(`${chatPath(companySlug, storeSlug)}/messages?after_seq=${Number(afterSeq) || 0}`, options);
}

export function sendChatMessage(companySlug, storeSlug, payload, options = {}) {
  return chatRequest(`${chatPath(companySlug, storeSlug)}/messages`, { ...options, method: "POST", body: payload });
}

export function markChatRead(companySlug, storeSlug, options = {}) {
  return chatRequest(`${chatPath(companySlug, storeSlug)}/read`, { ...options, method: "POST", body: {} });
}

export function uploadChatFile(companySlug, storeSlug, file, options = {}) {
  const form = new FormData();
  form.append("file", file, file.name || "upload");
  return chatRequest(`${chatPath(companySlug, storeSlug)}/upload`, { ...options, method: "POST", form });
}

export function reactToChatMessage(companySlug, storeSlug, messageId, emoji, options = {}) {
  return chatRequest(`${chatPath(companySlug, storeSlug)}/messages/${encodeURIComponent(messageId)}/reactions`, {
    ...options,
    method: "POST",
    body: { emoji },
  });
}

export function fetchMyChatConversations(token) {
  return get("/public/auth/chat/conversations", token);
}

// The stream hands the reader a URL and the headers to send with it, because
// EventSource cannot set an Authorization or X-Chat-Token header - only a real
// fetch can, and the reader in lib/chat.js does the parsing.
export function chatStreamUrl(companySlug, storeSlug, afterSeq = 0) {
  return `${base()}${chatPath(companySlug, storeSlug)}/stream?after_seq=${Number(afterSeq) || 0}`;
}

export { chatHeaders };
