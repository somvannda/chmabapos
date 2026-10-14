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

async function get(path) {
  const response = await fetch(`${base()}${path}`, { headers: { Accept: "application/json" } });
  if (response.status === 404) return null;
  if (!response.ok) throw new Response("Upstream request failed", { status: response.status });
  return response.json();
}

// The public payload for a store, addressed by its slugs. `null` means the
// address does not resolve to a published, active store.
export function fetchStore(companySlug, storeSlug) {
  return get(`/public/store/${encodeURIComponent(companySlug)}/${encodeURIComponent(storeSlug)}`);
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
