import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

// Guards the storefront switches in Settings -> Store settings -> All stores.
// Nothing here renders, and the component's gates are the part most likely to
// be lost in a later refactor - a switch that saves without re-checking the role
// gate, or a pause that sends a partial `storefront` document and silently wipes
// the merchant's branding. Both would look fine on screen, so a static check is
// what catches them.
const read = (relative) => readFileSync(new URL(relative, import.meta.url), "utf8").replace(/\r\n/g, "\n");

const settings = read("../features/settings.jsx");

test("the All stores card is gated on the same predicate the API enforces", () => {
  assert.match(
    settings,
    /const canManageStorefront = canEditSettingsSection\(memberRole, "Store settings"\);/,
    "the storefront controls must be gated by the settings-edit predicate, not an ad-hoc role check",
  );
  assert.match(
    settings,
    /\{canManageStorefront && <div className="rounded-2xl border border-\[#e9e9ef\] bg-white p-5 sm:p-6">/,
    "the All stores card must render behind canManageStorefront",
  );
});

test("every storefront write re-checks the gate before it saves", () => {
  for (const handler of ["setStoreOrdering", "setStoreListed", "setStoreAcceptOrders"]) {
    assert.match(
      settings,
      new RegExp("const " + handler + " = async \\(store, [^)]*\\) => \\{\\s*if \\(!canManageStorefront\\) return;"),
      `${handler} must bail out for a role that may not manage storefronts`,
    );
  }
});

test("the order pause sends the whole storefront document back", () => {
  // `update_store` assigns the payload onto the column, so a partial document
  // replaces the lot: tagline, logo, accent, hours. It must be merged in.
  assert.match(settings, /acceptOrdersPatch\(store\.storefront, accept\)/, "the pause must reuse the stored storefront");
  assert.ok(
    !/storefront: \{ accept_orders/.test(settings),
    "a partial storefront payload would wipe the merchant's branding",
  );
});

test("a disabled switch keeps its reason visible", () => {
  assert.match(settings, /reason=\{listing\.listBlockedReason\}/, "the listing switch must say why it is disabled");
  assert.match(settings, /reason=\{listing\.acceptBlockedReason\}/, "the pause switch must say why it is disabled");
});
