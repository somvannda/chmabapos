import test from "node:test";
import assert from "node:assert/strict";

import { slugifySku, isParentSkuLocked, suggestVariantSku } from "./sku.js";

test("slugifySku: uppercases and separates words with single dashes", () => {
  assert.equal(slugifySku("Iced Caffè Latte"), "ICED-CAFFE-LATTE");
});

test("slugifySku: strips punctuation and collapses repeated separators", () => {
  assert.equal(slugifySku('MacBook Pro 13" (Core i7)'), "MACBOOK-PRO-13-CORE-I7");
  assert.equal(slugifySku("  He--llo__World  "), "HE-LLO-WORLD");
});

test("slugifySku: returns an empty string when there is nothing usable", () => {
  assert.equal(slugifySku(""), "");
  assert.equal(slugifySku("   "), "");
  assert.equal(slugifySku("!!! ???"), "");
  assert.equal(slugifySku(null), "");
});

test("slugifySku: clamps to the max length", () => {
  assert.equal(slugifySku("abcdef", 4), "ABCD");
  assert.equal(slugifySku("ab-cd-ef", 5), "AB-CD");
});

test("suggestVariantSku: prefixes the product base SKU onto the variant name", () => {
  assert.equal(suggestVariantSku("MACBOOK-PRO14", "Space Gray 32GB/512GB"), "MACBOOK-PRO14-SPACE-GRAY-32GB-512GB");
  assert.equal(suggestVariantSku("café", "Latté Grande"), "CAFE-LATTE-GRANDE");
});

test("suggestVariantSku: tolerates a missing base or variant name", () => {
  assert.equal(suggestVariantSku("", "Midnight"), "MIDNIGHT");
  assert.equal(suggestVariantSku("COF-001", ""), "COF-001");
  assert.equal(suggestVariantSku(null, null), "");
});

test("suggestVariantSku: clamps to the max length without a dangling dash", () => {
  assert.equal(suggestVariantSku("ABC", "DEF", 6), "ABC-DE");
  assert.equal(suggestVariantSku("ABC", "DEF", 4), "ABC");
});

test("isParentSkuLocked: only variant products lock their base SKU", () => {
  assert.equal(isParentSkuLocked(0), false);
  assert.equal(isParentSkuLocked(1), true);
  assert.equal(isParentSkuLocked(undefined), false);
});
