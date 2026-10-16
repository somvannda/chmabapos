import test from "node:test";
import assert from "node:assert/strict";

import { categoryHref, categoryLabel } from "./categories.js";

test("categoryLabel: an API key becomes something a shopper can read", () => {
  assert.equal(categoryLabel("electronics"), "Electronics");
  assert.equal(categoryLabel("coffee-shop"), "Coffee shop");
  assert.equal(categoryLabel("sell_on_chmaba"), "Sell on chmaba");
});

test("categoryLabel: an empty or missing value produces nothing to show", () => {
  assert.equal(categoryLabel(""), "");
  assert.equal(categoryLabel(null), "");
  assert.equal(categoryLabel(undefined), "");
  assert.equal(categoryLabel("   "), "");
});

test("categoryHref: the value is encoded, so a key with a space still links", () => {
  assert.equal(categoryHref("electronics"), "/stores?vertical=electronics");
  assert.equal(categoryHref("coffee shop"), "/stores?vertical=coffee%20shop");
});
