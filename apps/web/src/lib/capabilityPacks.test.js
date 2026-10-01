import test from "node:test";
import assert from "node:assert/strict";

import { CAPABILITY_KEYS, CAPABILITY_PACKS, allowsCapability } from "./capabilityPacks.js";

test("capability packs have unique keys and a label and detail each", () => {
  assert.equal(new Set(CAPABILITY_KEYS).size, CAPABILITY_KEYS.length);
  assert.deepEqual(CAPABILITY_KEYS, CAPABILITY_PACKS.map((pack) => pack.key));
  for (const pack of CAPABILITY_PACKS) {
    assert.ok(pack.label, `pack ${pack.key} needs a label`);
    assert.ok(pack.detail, `pack ${pack.key} needs a detail`);
  }
});

test("the catalog covers every capability the UI gates on", () => {
  for (const key of ["barcode", "brand", "unit_of_measure", "variants", "modifiers", "tables", "serials", "batches"]) {
    assert.ok(CAPABILITY_KEYS.includes(key), `missing pack: ${key}`);
  }
});

test("allowsCapability fails open when the list is unknown", () => {
  assert.equal(allowsCapability(null, "serials"), true);
});

test("allowsCapability reflects the store's packs", () => {
  assert.equal(allowsCapability(["variants", "modifiers"], "modifiers"), true);
  assert.equal(allowsCapability(["variants", "modifiers"], "serials"), false);
  assert.equal(allowsCapability([], "tables"), false);
});
