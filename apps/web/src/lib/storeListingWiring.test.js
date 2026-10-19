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

test("the master switch is not named like the pause it governs", () => {
  // "Online ordering" and "Accepting orders" read as the same thing, which is
  // how a merchant turns off the whole store page meaning to pause lunch.
  assert.match(settings, /label="Public storefront"/, "the master must be named for the page, not for ordering");
  assert.ok(!/label="Online ordering"/.test(settings), "the ambiguous label must be gone from the row");
  assert.match(
    settings,
    /border-l-2 border-\[#eeeeF2\] pl-3\.5/,
    "the two switches that depend on the master must be visibly nested under it",
  );
});

test("hiding the public page asks first", () => {
  assert.match(settings, /const requestStoreOrdering = \(store, enabled\) => \{/, "the master toggle must go through the guard");
  assert.match(settings, /setHidePageTarget\(store\)/, "turning the master off must open the confirmation");
  assert.match(settings, /title="Hide this store's public page\?"/, "and the dialog must name what is being hidden");
});

test("every switch explains itself in text, not only on hover", () => {
  // `title` never appears on a tablet, which is where this screen is used.
  for (const label of ["Public storefront", "Listed in directory", "Accepting orders"]) {
    assert.match(settings, new RegExp(`StorefrontSwitch label="${label}" help="`), `${label} must explain itself in place`);
  }
  assert.match(settings, /\{help && <span/, "the help prop must render as a visible line");
});

test("the row states the outcome, not just three checkboxes", () => {
  assert.match(settings, /storeListingSummary\(listing\)/, "the row must derive its chip from the gate helper");
  assert.match(settings, /<Badge tone=\{summary\.tone\} dot>\{summary\.label\}<\/Badge>/, "the chip must be rendered");
  assert.match(settings, /\{gapNote && <p/, "a listed store missing a logo or hours must be called out");
});

test("only a restaurant gets the directory box pre-ticked when adding a store", () => {
  assert.match(
    settings,
    /listed_in_directory: defaultListedInDirectory\(workspace\?\.company\?\.vertical\)/,
    "the add form must derive the default from the shop type, in code, not in prose",
  );
  assert.match(
    settings,
    /checked=\{Boolean\(newStore\.listed_in_directory\)\}/,
    "the default must be a visible checkbox the merchant can untick, never a hidden server default",
  );
});
