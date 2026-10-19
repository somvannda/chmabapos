// A store's canonical address, and the redirect decision that keeps it a single
// address.
//
// Slugs are merchant-editable, and a rename keeps the old value resolving so a
// link already printed or shared never 404s. The API answers a retired address
// with the store's *current* slugs, so the page can send the visitor on to the
// address the store uses now. That is what keeps the URL bar, the share sheet and
// the crawler in agreement, and what makes `previous_slugs` worth storing.

/** The canonical `{ company, store }` segments, or null when either is missing. */
export function storeAddress(store) {
  const company = (store?.company_slug || "").trim();
  const slug = (store?.store_slug || "").trim();
  return company && slug ? { company, store: slug } : null;
}

/**
 * The path a store page should live at, or null when the requested address is
 * already canonical (so the caller renders instead of redirecting).
 *
 * A table context and a product id travel in the path rather than being dropped,
 * so a shared link that included them lands on the right page after a rename.
 */
export function canonicalRedirect(store, params = {}, { tableCode, productId } = {}) {
  const address = storeAddress(store);
  if (!address) return null;
  if (address.company === params.companySlug && address.store === params.storeSlug) return null;
  const base = `/${address.company}/${address.store}`;
  if (productId) return `${base}/product/${encodeURIComponent(productId)}`;
  if (tableCode) return `${base}/t/${encodeURIComponent(tableCode)}`;
  return base;
}
