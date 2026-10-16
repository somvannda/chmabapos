import test from "node:test";
import assert from "node:assert/strict";

import { applyDelta, cartCount, cartKey, readCart } from "./cart.js";

test("cartKey: scoped per store, so one shop never shows another's lines", () => {
  assert.notEqual(cartKey("acme", "main"), cartKey("acme", "second"));
  assert.match(cartKey("acme", "main"), /acme\/main$/);
});

test("cartKey: a missing slug gives a usable key rather than 'undefined'", () => {
  assert.equal(cartKey(undefined, undefined), "chmaba.cart:/");
});

test("readCart: with no browser there is simply no cart", () => {
  // Node has no window, which is exactly the server-render path.
  assert.deepEqual(readCart("chmaba.cart:anything"), {});
});

test("applyDelta: adds, removes, and drops a line that reaches zero", () => {
  assert.deepEqual(applyDelta({}, "a", 1), { a: 1 });
  assert.deepEqual(applyDelta({ a: 1 }, "a", 1), { a: 2 });
  assert.deepEqual(applyDelta({ a: 2 }, "a", -1), { a: 1 });
  // The key disappearing rather than sitting at 0 is what keeps empty lines out of the
  // cart bar and out of the order payload.
  assert.deepEqual(applyDelta({ a: 1 }, "a", -1), {});
});

test("applyDelta: never goes negative", () => {
  assert.deepEqual(applyDelta({ a: 1 }, "a", -5), {});
});

test("applyDelta: leaves the other lines alone", () => {
  assert.deepEqual(applyDelta({ a: 1, b: 3 }, "a", 1), { a: 2, b: 3 });
});

test("applyDelta: a junk quantity counts as nothing rather than being trusted", () => {
  assert.deepEqual(applyDelta({ a: "nonsense" }, "a", 1), { a: 1 });
});

test("cartCount: totals the quantities, not the number of lines", () => {
  assert.equal(cartCount({ a: 2, b: 3 }), 5);
  assert.equal(cartCount({}), 0);
});
