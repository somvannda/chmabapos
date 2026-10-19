import test from "node:test";
import assert from "node:assert/strict";

import {
  STORE_LISTING_REASONS,
  acceptOrdersPatch,
  listingPatch,
  orderingPatch,
  storeListingState,
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
