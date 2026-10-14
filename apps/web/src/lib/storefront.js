// Public storefront address helpers.
//
// Stores have their own public origin (for example shops.chmaba.com), so the
// canonical address for a store is `<origin>/<company-slug>/<store-slug>` rather
// than the legacy `/order/<token>` link. `VITE_STOREFRONT_URL` stays blank until
// that host exists, and every caller falls back to the legacy link so nothing
// breaks in the meantime.

export const STOREFRONT_BASE_URL = (import.meta.env.VITE_STOREFRONT_URL || "").replace(/\/+$/, "");

// Canonical store page, or "" when the storefront host or a slug is missing.
export function storefrontUrl(companySlug, storeSlug, { tableToken } = {}) {
  const company = (companySlug || "").trim();
  const store = (storeSlug || "").trim();
  if (!STOREFRONT_BASE_URL || !company || !store) return "";
  const path = `${STOREFRONT_BASE_URL}/${company}/${store}`;
  return tableToken ? `${path}?table=${encodeURIComponent(tableToken)}` : path;
}

// The legacy tokenised link. Kept working forever: printed table QR codes and
// links already shared by merchants point at it, and it redirects to the
// canonical address above.
export function legacyOrderUrl(token, origin = typeof window !== "undefined" ? window.location.origin : "") {
  return token ? `${origin}/order/${token}` : "";
}
