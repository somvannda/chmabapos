import test from "node:test";
import assert from "node:assert/strict";

import { computeDiscount, serialCandidatesFor, enabledCompanyCurrencies, matchScan, normalizeScanTerm } from "./posMath.js";

test("discount: percent mode multiplies the subtotal", () => {
  assert.equal(computeDiscount(600, "percent", "30"), 180);
});

test("discount: amount mode is a flat value, not a percentage", () => {
  assert.equal(computeDiscount(600, "amount", "30"), 30);
});

test("discount: amount mode clamps to the subtotal", () => {
  assert.equal(computeDiscount(600, "amount", "700"), 600);
});

test("discount: percent mode clamps at 100%", () => {
  assert.equal(computeDiscount(600, "percent", "150"), 600);
});

test("discount: blank or negative input is zero", () => {
  assert.equal(computeDiscount(480, "amount", ""), 0);
  assert.equal(computeDiscount(480, "percent", "-5"), 0);
});

test("serial candidates: keeps unattributed and matching units, drops other stores/variants", () => {
  const storeId = "store-1";
  const variantId = "variant-1";
  const rows = [
    { id: "a", store_id: storeId, variant_id: variantId },
    { id: "b", store_id: null, variant_id: null },
    { id: "c", store_id: "store-2", variant_id: variantId },
    { id: "d", store_id: storeId, variant_id: "variant-2" },
  ];
  assert.deepEqual(serialCandidatesFor(rows, { storeId, variantId }).map((row) => row.id), ["a", "b"]);
});

test("serial candidates: a non-variant line only accepts unattributed units", () => {
  const rows = [
    { id: "a", store_id: null, variant_id: null },
    { id: "b", store_id: null, variant_id: "variant-1" },
  ];
  assert.deepEqual(serialCandidatesFor(rows, { storeId: "store-1", variantId: null }).map((row) => row.id), ["a"]);
});

test("enabled currencies: only enabled rows are offered", () => {
  const rows = [
    { is_enabled: true, currency: { code: "USD" } },
    { is_enabled: false, currency: { code: "KHR" } },
    { is_enabled: true, currency: { code: "THB" } },
  ];
  assert.deepEqual(enabledCompanyCurrencies(rows).map((c) => c.code), ["USD", "THB"]);
});

test("scan match: normalizes case, spaces and non-strings", () => {
  assert.equal(normalizeScanTerm("  AbC-123 "), "abc-123");
  assert.equal(normalizeScanTerm(null), "");
  assert.equal(normalizeScanTerm(undefined), "");
});

test("scan match: a serial wins over a product with the same code", () => {
  const products = [{ sku: "SN-1", barcode: null, id: "p1" }];
  const serials = [{ id: "s1", serial_number: "SN-1", imei: null }];
  const match = matchScan("sn-1", { products, serials });
  assert.equal(match.kind, "serial");
  assert.equal(match.serial.id, "s1");
});

test("scan match: matches a product by SKU or barcode", () => {
  const products = [
    { id: "p1", sku: "SKU-1", barcode: "BC-1" },
    { id: "p2", sku: "SKU-2", barcode: "BC-2" },
  ];
  assert.equal(matchScan("SKU-2", { products }).product.id, "p2");
  assert.equal(matchScan(" bc-1 ", { products }).product.id, "p1");
});

test("scan match: matches a unit by IMEI", () => {
  const serials = [{ id: "s1", serial_number: "SN-1", imei: "356789012345678" }];
  const match = matchScan("356789012345678", { serials });
  assert.equal(match.kind, "serial");
  assert.equal(match.serial.id, "s1");
});

test("scan match: partial and blank terms do not resolve", () => {
  const products = [{ id: "p1", sku: "SKU-1", barcode: null }];
  assert.equal(matchScan("SKU", { products }), null);
  assert.equal(matchScan("", { products }), null);
  assert.equal(matchScan("   ", { products }), null);
});
