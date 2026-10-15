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
export function fetchDirectory({ q = "", vertical = "", limit = 24, offset = 0 } = {}) {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  if (q.trim()) params.set("q", q.trim());
  if (vertical.trim()) params.set("vertical", vertical.trim());
  return get(`/public/stores?${params.toString()}`);
}

// Place an order against the storefront address. Prices are never sent: the API
// prices every line from the catalogue.
export function submitStoreOrder(companySlug, storeSlug, payload) {
  return post(`/public/store/${encodeURIComponent(companySlug)}/${encodeURIComponent(storeSlug)}/orders`, payload);
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
