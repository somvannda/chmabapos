import test from "node:test";
import assert from "node:assert/strict";

import {
  DIRECTORY_DEFAULT_VERTICALS,
  STORE_LISTING_REASONS,
  acceptOrdersPatch,
  defaultListedInDirectory,
  listingPatch,
  orderingPatch,
  storeListingState,
  storeListingSummary,
  storefrontGapNote,
  storefrontGaps,
} from "./storeListing.js";

const liveStore = (overrides = {}) => ({
  id: "store-1",
  is_active: true,
  slug: "riverside",
  public_order_enabled: true,
  listed_in_directory: false,
  storefront: null,
  ...overrides,
});

test("an active store with ordering on and an address can use every switch", () => {
  const state = storeListingState(liveStore());
  assert.equal(state.canToggleOrdering, true);
  assert.equal(state.canList, true);
  assert.equal(state.canAcceptOrders, true);
  assert.equal(state.listBlockedReason, null);
  assert.equal(state.acceptBlockedReason, null);
});

test("listing is blocked while online ordering is off, accepting is too", () => {
  const state = storeListingState(liveStore({ public_order_enabled: false }));
  assert.equal(state.canToggleOrdering, true, "the master switch stays usable");
  assert.equal(state.canList, false);
  assert.equal(state.canAcceptOrders, false);
  assert.equal(state.listBlockedReason, STORE_LISTING_REASONS.orderingOff);
  assert.equal(state.acceptBlockedReason, STORE_LISTING_REASONS.orderingOff);
});

test("listing is blocked without a public address, because the card has nothing to link to", () => {
  const state = storeListingState(liveStore({ slug: null }));
  assert.equal(state.canList, false);
  assert.equal(state.listBlockedReason, STORE_LISTING_REASONS.noAddress);
  assert.equal(state.canAcceptOrders, true, "a store can still take orders from its tokenised link");
});

test("a blank slug counts as no address", () => {
  assert.equal(storeListingState(liveStore({ slug: "   " })).canList, false);
});

test("an inactive store cannot use any switch", () => {
  const state = storeListingState(liveStore({ is_active: false }));
  assert.equal(state.canToggleOrdering, false);
  assert.equal(state.canList, false);
  assert.equal(state.canAcceptOrders, false);
  assert.equal(state.listBlockedReason, STORE_LISTING_REASONS.inactive);
  assert.equal(state.acceptBlockedReason, STORE_LISTING_REASONS.inactive);
});

test("deactivation outranks the missing-address reason", () => {
  const state = storeListingState({ is_active: false, public_order_enabled: true, slug: null });
  assert.equal(state.listBlockedReason, STORE_LISTING_REASONS.inactive);
});

test("the stored flags are reported, not the effective ones", () => {
  // Ordering off hides the store from the directory, but the owner's listing
  // choice is preserved so turning ordering back on restores it.
  const state = storeListingState(liveStore({ public_order_enabled: false, listed_in_directory: true }));
  assert.equal(state.listed, true);
});

test("accepting orders is on unless the storefront explicitly paused it", () => {
  assert.equal(storeListingState(liveStore()).acceptOrders, true);
  assert.equal(storeListingState(liveStore({ storefront: {} })).acceptOrders, true);
  assert.equal(storeListingState(liveStore({ storefront: { accept_orders: true } })).acceptOrders, true);
  assert.equal(storeListingState(liveStore({ storefront: { accept_orders: false } })).acceptOrders, false);
});

test("a missing store is treated as unusable rather than throwing", () => {
  const state = storeListingState(undefined);
  assert.equal(state.canList, false);
  assert.equal(state.canAcceptOrders, false);
});

test("the patches carry exactly the field each control owns", () => {
  assert.deepEqual(orderingPatch(true), { enabled: true });
  assert.deepEqual(orderingPatch(undefined), { enabled: false });
  assert.deepEqual(listingPatch(true), { listed_in_directory: true });
  assert.deepEqual(listingPatch(0), { listed_in_directory: false });
});

test("the pause patch keeps the rest of the branding document", () => {
  // `storefront` is stored whole. A partial document would wipe the merchant's
  // tagline, logo, hours and accent, so this is the regression that matters.
  const storefront = {
    tagline: "Roasted daily",
    accent: "violet",
    logo: "/media/logo.png",
    hours: [{ day: "mon", open: "09:00", close: "21:00", closed: false }],
    socials: { telegram: "@shop" },
  };
  const patch = acceptOrdersPatch(storefront, false);
  assert.deepEqual(patch.storefront, { ...storefront, accept_orders: false });
  assert.equal(storefront.accept_orders, undefined, "the caller's object must not be mutated");
});

test("pausing an empty storefront still produces a valid document", () => {
  assert.deepEqual(acceptOrdersPatch(null, false), { storefront: { accept_orders: false } });
});

test("the summary chip names the outcome of all three switches", () => {
  const row = (overrides) => storeListingSummary(storeListingState(liveStore(overrides)));
  assert.deepEqual(row({ is_active: false }), { label: "Offline", tone: "neutral" });
  assert.deepEqual(row({ public_order_enabled: false }), { label: "Not public", tone: "neutral" });
  assert.deepEqual(row({ listed_in_directory: true, storefront: { accept_orders: false } }), {
    label: "Listed, paused",
    tone: "yellow",
  });
  assert.deepEqual(row({ storefront: { accept_orders: false } }), { label: "Paused", tone: "yellow" });
  assert.deepEqual(row({ listed_in_directory: true }), { label: "Live & listed", tone: "green" });
  assert.deepEqual(row({}), { label: "Live, unlisted", tone: "blue" });
});

test("a store that cannot be seen is never described as live", () => {
  // Ordering off wins over the other flags when naming the state: the directory
  // filter and the public page both need ordering, so "Live" would be a lie.
  const off = storeListingSummary(storeListingState(liveStore({ public_order_enabled: false, listed_in_directory: true })));
  assert.equal(off.label, "Not public");
});

test("gaps are only what a shopper would notice is missing", () => {
  assert.deepEqual(storefrontGaps(liveStore()), ["logo", "opening hours"]);
  assert.deepEqual(storefrontGaps(liveStore({ storefront: { logo: "/media/l.png" } })), ["opening hours"]);
  assert.deepEqual(storefrontGaps(liveStore({ storefront: { hours: [{ day: "mon" }] } })), ["logo"]);
  assert.deepEqual(
    storefrontGaps(liveStore({ storefront: { logo: "/media/l.png", hours: [{ day: "mon" }] } })),
    [],
  );
});

test("a gap note only appears for a listed store, and only when something is missing", () => {
  assert.equal(storefrontGapNote(liveStore(), { listed: true }), "Listed, but the card has no logo or opening hours yet.");
  assert.equal(
    storefrontGapNote(liveStore({ storefront: { logo: "/media/l.png" } }), { listed: true }),
    "Listed, but the card has no opening hours yet.",
  );
  assert.equal(storefrontGapNote(liveStore({ storefront: { hours: [{}] } }), { listed: true }), "Listed, but the card has no logo yet.");
  const complete = liveStore({ storefront: { logo: "/media/l.png", hours: [{}] } });
  assert.equal(storefrontGapNote(complete, { listed: true }), null);
  assert.equal(storefrontGapNote(liveStore(), { listed: false }), null, "an unlisted store has no card to spoil");
});

test("only a restaurant pre-ticks the directory box", () => {
  assert.deepEqual(DIRECTORY_DEFAULT_VERTICALS, ["restaurant"]);
  assert.equal(defaultListedInDirectory("restaurant"), true);
  assert.equal(defaultListedInDirectory("  Restaurant "), true);
  assert.equal(defaultListedInDirectory("coffee"), false, "cafés were not part of the ask");
  assert.equal(defaultListedInDirectory("general"), false);
  assert.equal(defaultListedInDirectory(undefined), false);
  assert.equal(defaultListedInDirectory(""), false);
});
