import { test } from "node:test";
import assert from "node:assert/strict";

import { storeQrFileName } from "./storeQr.js";

test("a store name becomes a friendly PNG filename", () => {
  assert.equal(storeQrFileName("Acme Coffee"), "acme-coffee-qr.png");
  assert.equal(storeQrFileName("  Riverside Store!  "), "riverside-store-qr.png");
  assert.equal(storeQrFileName("Store #1"), "store-1-qr.png");
});

test("accents fold instead of producing odd separators", () => {
  assert.equal(storeQrFileName("Café Sralanh"), "cafe-sralanh-qr.png");
});

test("a name with no Latin characters still gets a usable file", () => {
  // Khmer shop names are common; an empty filename would make the browser save
  // something like "-qr.png".
  assert.equal(storeQrFileName("ហាងកាហ្វេ"), "store-qr.png");
  assert.equal(storeQrFileName(""), "store-qr.png");
  assert.equal(storeQrFileName(null), "store-qr.png");
});

test("very long names stay short enough for a download", () => {
  const name = storeQrFileName("A".repeat(200));
  assert.ok(name.length <= 67, name);
  assert.ok(name.endsWith("-qr.png"));
  assert.ok(!name.includes("--"), "no doubled separators");
});
