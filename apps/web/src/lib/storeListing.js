// Per-store storefront controls (Settings -> Store settings -> All stores).
//
// Three switches decide whether a store can be found and ordered from. They are
// not interchangeable, and only one of them is a prerequisite for the others:
//
//   * online ordering (`public_order_enabled`) - the store has a public page at
//     all. This is the master switch: with it off the public page 404s and the
//     directory skips the store.
//   * listed in the directory (`listed_in_directory`) - the store is
//     discoverable on the public Stores page. Opt-in, so a storefront that is
//     reachable by its own shared link stays out of the directory until the
//     owner says otherwise.
//   * accepting orders (`storefront.accept_orders`) - a temporary pause for a
//     kitchen at capacity. The menu keeps showing; the order button does not.
//
// The gates here mirror `chmabapos_api/app/api/v1.py`: `list_public_stores` only
// returns a store when it is active, its company is active, online ordering is
// on and both slugs exist, and the public page itself refuses to render while
// online ordering is off.
//
// This is the *prerequisite* check, not a permission check. Permission is the
// owner-only Settings section plus `settings_manage_roles` on the API (any role
// holding `settings.manage`). A control whose prerequisite is missing is
// disabled and says why, rather than being hidden and leaving the merchant
// hunting for it, or left enabled and failing on save.
//
// The flags are deliberately not cascaded: switching online ordering off leaves
// `listed_in_directory` and `accept_orders` exactly as the owner set them, so
// turning ordering back on restores the previous state. Clearing them instead
// would silently unlist a store whose address is printed on signage.

export const STORE_LISTING_REASONS = {
  inactive: "Reactivate this store first",
  orderingOff: "Turn on online ordering for this store first",
  noAddress: "This store has no web address yet",
};

const nonEmpty = (value) => typeof value === "string" && value.trim() !== "";

// What a store's row may do, and why not when it may not.
export function storeListingState(store) {
  const source = store || {};
  const active = Boolean(source.is_active);
  const ordering = Boolean(source.public_order_enabled);
  const hasAddress = nonEmpty(source.slug);
  // Only an explicit false pauses ordering; anything else (including a store
  // that never touched the editor) means open. Matches the storefront app.
  const acceptOrders = !(source.storefront && source.storefront.accept_orders === false);

  // Both follow-on switches need online ordering, and listing additionally
  // needs a public address for the directory card to link to.
  const inactiveReason = active ? null : STORE_LISTING_REASONS.inactive;
  const listBlockedReason =
    inactiveReason ||
    (ordering ? null : STORE_LISTING_REASONS.orderingOff) ||
    (hasAddress ? null : STORE_LISTING_REASONS.noAddress);
  const acceptBlockedReason = inactiveReason || (ordering ? null : STORE_LISTING_REASONS.orderingOff);

  return {
    active,
    ordering,
    hasAddress,
    listed: Boolean(source.listed_in_directory),
    acceptOrders,
    canToggleOrdering: active,
    canList: listBlockedReason === null,
    listBlockedReason,
    canAcceptOrders: acceptBlockedReason === null,
    acceptBlockedReason,
  };
}

// `public_order_enabled` is not part of the store update payload: enabling a
// store also mints its public order token, so it has its own endpoint.
export function orderingPatch(enabled) {
  return { enabled: Boolean(enabled) };
}

export function listingPatch(listed) {
  return { listed_in_directory: Boolean(listed) };
}

// `storefront` is stored whole, not merged - `update_store` assigns the payload
// straight onto the column, and the input model fills `socials`/`policies`/
// `hours` with their defaults. A partial document would therefore drop every
// other branding field the merchant saved. The pause has to send the existing
// document back with one field changed.
export function acceptOrdersPatch(storefront, acceptOrders) {
  return { storefront: { ...(storefront || {}), accept_orders: Boolean(acceptOrders) } };
}

// The row also states the outcome in one sentence. Three interdependent
// checkboxes are hard to hold in your head and invite the wrong reading - "I
// turned accepting orders off, so my store is closed" - so the chip names the
// result instead.
export function storeListingSummary(state) {
  const store = state || {};
  if (!store.active) return { label: "Offline", tone: "neutral" };
  if (!store.ordering) return { label: "Not public", tone: "neutral" };
  if (!store.acceptOrders) return { label: store.listed ? "Listed, paused" : "Paused", tone: "yellow" };
  return store.listed
    ? { label: "Live & listed", tone: "green" }
    : { label: "Live, unlisted", tone: "blue" };
}

// What the public card will be missing. A listed store with no logo or hours is a
// bare entry in the directory - the thing the opt-in exists to prevent - so the
// row says so before a shopper finds it, not after.
export function storefrontGaps(store) {
  const brand = (store || {}).storefront || {};
  const gaps = [];
  if (!brand.logo) gaps.push("logo");
  if (!Array.isArray(brand.hours) || brand.hours.length === 0) gaps.push("opening hours");
  return gaps;
}

export function storefrontGapNote(store, { listed } = {}) {
  if (!listed) return null;
  const gaps = storefrontGaps(store);
  if (gaps.length === 0) return null;
  const missing = gaps.length === 1 ? gaps[0] : `${gaps[0]} or ${gaps[1]}`;
  return `Listed, but the card has no ${missing} yet.`;
}

// Shop types whose owners most often want to be found. The Add store form offers
// the directory checkbox already ticked for these. It stays visible and the
// merchant can untick it, so this is a default rather than a policy - and it is
// inert on its own, because the directory needs online ordering as well.
export const DIRECTORY_DEFAULT_VERTICALS = ["restaurant"];

export const defaultListedInDirectory = (vertical) =>
  DIRECTORY_DEFAULT_VERTICALS.includes((vertical || "").trim().toLowerCase());
