// The shopper's cart, kept in sessionStorage.
//
// It lives outside the component because two routes need the same one: the store page and
// a product page, and a cart that empties when you open a product is not a cart. Session
// storage rather than local, so a half-finished order does not quietly reappear weeks
// later, and keyed per store so looking at one shop never shows another's lines.
//
// Quantities only, never prices: the API reprices every line from the catalogue when the
// order is submitted, so a price cached in the browser could only ever be a lie.

const PREFIX = "chmaba.cart";

/** Broadcast when this tab changes the cart, so open components re-read it. */
export const CART_EVENT = "chmaba:cart";

export function cartKey(companySlug, storeSlug) {
  return `${PREFIX}:${companySlug || ""}/${storeSlug || ""}`;
}

function usable(value) {
  const quantity = Number(value);
  return Number.isFinite(quantity) && quantity > 0 ? Math.floor(quantity) : 0;
}

export function readCart(storageKey) {
  if (typeof window === "undefined") return {};
  try {
    const parsed = JSON.parse(window.sessionStorage.getItem(storageKey) || "{}");
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) return {};
    // Drop anything that is not a positive whole number, so a half-written or
    // hand-edited value can never reach an order.
    return Object.fromEntries(
      Object.entries(parsed)
        .map(([lineKey, quantity]) => [lineKey, usable(quantity)])
        .filter(([, quantity]) => quantity > 0),
    );
  } catch {
    return {};
  }
}

export function writeCart(storageKey, cart) {
  if (typeof window === "undefined") return;
  try {
    window.sessionStorage.setItem(storageKey, JSON.stringify(cart));
  } catch {
    // Private mode can refuse storage; the cart then simply does not survive navigation.
  }
  window.dispatchEvent(new Event(CART_EVENT));
}

/** One line's quantity changed by `delta`; a line that reaches zero is dropped. */
export function applyDelta(cart, lineKey, delta) {
  const next = { ...cart };
  const quantity = Math.max(0, (usable(next[lineKey]) || 0) + delta);
  if (quantity) next[lineKey] = quantity;
  else delete next[lineKey];
  return next;
}

export function cartCount(cart) {
  return Object.values(cart).reduce((sum, quantity) => sum + (Number(quantity) || 0), 0);
}
