import test from "node:test";
import assert from "node:assert/strict";

import { findSupplierQuote, preferredSupplierQuote, suggestedUnitCost } from "./purchaseCost.js";

const prices = [
  { supplier_id: "a", variant_id: "v1", unit_cost: "120.00", is_preferred: false },
  { supplier_id: "b", variant_id: "v1", unit_cost: "132.50", is_preferred: true },
  { supplier_id: "a", variant_id: "v2", unit_cost: "99.00", is_preferred: true },
  { supplier_id: "a", variant_id: null, unit_cost: "5.25", is_preferred: false },
];

test("a line uses the cost of the supplier it is ordered from", () => {
  assert.deepEqual(suggestedUnitCost(prices, { variantId: "v1", supplierId: "a" }), {
    unitCost: "120.00",
    source: "supplier",
    quote: prices[0],
  });
  assert.equal(suggestedUnitCost(prices, { variantId: "v1", supplierId: "b" }).unitCost, "132.50");
});

test("without a chosen supplier the preferred quote is only a starting point", () => {
  const suggestion = suggestedUnitCost(prices, { variantId: "v1" });
  assert.equal(suggestion.unitCost, "132.50");
  assert.equal(suggestion.source, "preferred");
});

test("a supplier quote never leaks across variants", () => {
  // Supplier "a" prices v1 at 120 and v2 at 99; picking v2 must not reuse v1.
  assert.equal(suggestedUnitCost(prices, { variantId: "v2", supplierId: "a" }).unitCost, "99.00");
  // Supplier "b" has no quote for v2, so the preferred v2 quote (also "a") wins.
  assert.equal(suggestedUnitCost(prices, { variantId: "v2", supplierId: "b" }).unitCost, "99.00");
});

test("a product without variants reads the product-level quote", () => {
  assert.equal(suggestedUnitCost(prices, { supplierId: "a" }).unitCost, "5.25");
  // A product-level quote must not be applied to a variant line.
  assert.equal(findSupplierQuote(prices, { variantId: "v1", supplierId: "a" }).unit_cost, "120.00");
  assert.equal(findSupplierQuote(prices, { supplierId: "b" }), null);
});

test("no quote leaves the field empty instead of guessing a cost", () => {
  const suggestion = suggestedUnitCost(prices, { variantId: "v3", supplierId: "a" });
  assert.equal(suggestion.unitCost, "");
  assert.equal(suggestion.source, "none");
  assert.equal(suggestedUnitCost([], { variantId: "v1" }).source, "none");
  assert.equal(suggestedUnitCost(null, { variantId: "v1" }).unitCost, "");
});

test("a zero cost is a real cost, not a missing one", () => {
  const free = [{ supplier_id: "a", variant_id: "v1", unit_cost: "0.00", is_preferred: false }];
  assert.equal(suggestedUnitCost(free, { variantId: "v1", supplierId: "a" }).unitCost, "0.00");
  assert.equal(preferredSupplierQuote(free, "v1"), null);
});
