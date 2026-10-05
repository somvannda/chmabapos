import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

// Guards a real regression: the "Default tender at checkout" POS preference was
// saved by settings.jsx but never handed to the register, so checkout always
// opened on Cash. Rendering is not available in this suite, so these static
// checks pin the wiring down.
const workspace = readFileSync(
  new URL("../features/workspace.jsx", import.meta.url),
  "utf8",
).replace(/\r\n/g, "\n");
const sales = readFileSync(
  new URL("../features/sales.jsx", import.meta.url),
  "utf8",
).replace(/\r\n/g, "\n");

test("default tender: workspace forwards the store preference to the register", () => {
  assert.match(
    workspace,
    /<LivePOSView[^>]*defaultTenderMethod=\{storePrefs\.default_tender_method === "khqr" \? "khqr" : "cash"\}/,
    "workspace must pass defaultTenderMethod from store preferences to LivePOSView",
  );
});

test("default tender: register accepts the prop and seeds the first tender", () => {
  assert.match(
    sales,
    /function LivePOSView\(\{[^}]*defaultTenderMethod\s*=\s*"cash"[^}]*\}\)/,
    "LivePOSView must accept defaultTenderMethod with a cash default",
  );
  assert.match(
    sales,
    /useState\(\[\{ method: defaultTenderMethod,/,
    "the first tender row must be seeded from defaultTenderMethod",
  );
});
