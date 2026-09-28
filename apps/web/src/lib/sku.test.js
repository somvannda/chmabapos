import test from "node:test";
import assert from "node:assert/strict";

import { slugifySku, isParentSkuLocked } from "./sku.js";

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

test("isParentSkuLocked: only variant products lock their base SKU", () => {
  assert.equal(isParentSkuLocked(0), false);
  assert.equal(isParentSkuLocked(1), true);
  assert.equal(isParentSkuLocked(undefined), false);
});
