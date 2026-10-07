import test from "node:test";
import assert from "node:assert/strict";

import { buildCartLinesFromFailed, failedItemLabel, mergeCartLines } from "./offlineReconcile.js";

const PRODUCTS = [
  { id: "p1", name: "Coffee", price: 3, stock: 5, lineKey: "p1:", variant_id: null },
  { id: "p2", name: "Cake", price: 4, stock: 0, lineKey: "p2:", variant_id: null },
  { id: "p1", name: "Coffee · Large", price: 4.5, stock: 2, lineKey: "p1:v1", variant_id: "v1" },
];

test("offlineReconcile: rebuilds sellable lines and reports the rest as skipped", () => {
  const body = {
    items: [
      { product_id: "p1", variant_id: null, quantity: 2 },
      { product_id: "p2", variant_id: null, quantity: 1 }, // out of stock
      { product_id: "gone", variant_id: null, quantity: 1 }, // missing
      { combo_id: "c1", quantity: 1 }, // combo
      { product_id: "p1", variant_id: "v1", quantity: 5 }, // variant, capped to stock 2
    ],
  };
  const { lines, skipped } = buildCartLinesFromFailed(body, PRODUCTS);
  assert.equal(lines.length, 2);
  assert.equal(lines[0].lineKey, "p1:#");
  assert.equal(lines[0].quantity, 2);
  assert.equal(lines[0].price, 3);
  assert.equal(lines[1].lineKey, "p1:v1#");
  assert.equal(lines[1].quantity, 2); // capped from 5 to available stock
  assert.equal(lines[1].price, 4.5);
  assert.deepEqual(skipped.map((entry) => entry.reason), ["stock", "missing", "combo"]);
});

test("offlineReconcile: modifiers adjust price and the line key", () => {
  const body = { items: [{ product_id: "p1", variant_id: null, quantity: 1, modifiers: [{ name: "Shot", price_delta: "0.5" }, { name: "Soy", price_delta: 1 }] }] };
  const { lines } = buildCartLinesFromFailed(body, PRODUCTS);
  assert.equal(lines.length, 1);
  assert.equal(lines[0].price, 4.5); // 3 + 0.5 + 1
  assert.equal(lines[0].lineKey, "p1:#Shot:0.5|Soy:1");
});

test("offlineReconcile: tolerates a missing body", () => {
  assert.deepEqual(buildCartLinesFromFailed(undefined, PRODUCTS), { lines: [], skipped: [] });
  assert.deepEqual(buildCartLinesFromFailed({ items: [] }, []), { lines: [], skipped: [] });
});

test("offlineReconcile: mergeCartLines appends new lines and merges duplicates up to stock", () => {
  const existing = [{ lineKey: "p1:#", id: "p1", quantity: 1, stock: 5 }];
  const incoming = [
    { lineKey: "p1:#", id: "p1", quantity: 2, stock: 5 },
    { lineKey: "p3:#", id: "p3", quantity: 3, stock: 10 },
  ];
  const merged = mergeCartLines(existing, incoming);
  assert.equal(merged.length, 2);
  assert.equal(merged[0].quantity, 3); // 1 + 2
  assert.equal(merged[1].quantity, 3);
});

test("offlineReconcile: mergeCartLines caps a merged quantity at stock", () => {
  const existing = [{ lineKey: "p1:#", id: "p1", quantity: 4, stock: 5 }];
  const incoming = [{ lineKey: "p1:#", id: "p1", quantity: 4, stock: 5 }];
  const merged = mergeCartLines(existing, incoming);
  assert.equal(merged[0].quantity, 5);
});

test("offlineReconcile: labels a line from the catalogue, falling back gracefully", () => {
  assert.equal(failedItemLabel({ product_id: "p1", variant_id: null }, PRODUCTS), "Coffee");
  assert.equal(failedItemLabel({ product_id: "p1", variant_id: "v1" }, PRODUCTS), "Coffee · Large");
  assert.equal(failedItemLabel({ combo_id: "c1" }, [{ combo_id: "c1", name: "Breakfast set" }]), "Breakfast set");
  assert.equal(failedItemLabel({ product_id: "gone", variant_id: null }, PRODUCTS), "Item");
  assert.equal(failedItemLabel({ product_id: "gone", name: "Custom" }, PRODUCTS), "Custom");
  assert.equal(failedItemLabel({ combo_id: "c9" }, PRODUCTS), "Combo");
});
