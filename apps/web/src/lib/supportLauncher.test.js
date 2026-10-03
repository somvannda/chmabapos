import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

// Guards a real regression: the global "Ask Chmaba" launcher is fixed to the
// bottom-right of every workspace page, which covers the POS "Charge" button.
// The launcher must stay hidden on the POS view (activeView === "pos") while
// remaining reachable everywhere else. Rendering is not available in this
// suite, so this static check pins the wiring down.
const launcher = readFileSync(
  new URL("../components/SupportLauncher.jsx", import.meta.url),
  "utf8",
).replace(/\r\n/g, "\n");
const workspace = readFileSync(
  new URL("../features/workspace.jsx", import.meta.url),
  "utf8",
).replace(/\r\n/g, "\n");

test("support launcher: accepts a hidden prop defaulting to visible", () => {
  assert.match(
    launcher,
    /function SupportLauncher\(\{[^}]*hidden\s*=\s*false[^}]*\}\)/,
    "SupportLauncher must accept hidden with a false default so other pages stay unchanged",
  );
});

test("support launcher: renders nothing when hidden", () => {
  assert.match(
    launcher,
    /if \(hidden\) return null;/,
    "SupportLauncher must bail out before rendering when hidden",
  );
});

test("support launcher: is hidden on the POS view", () => {
  assert.match(
    workspace,
    /<SupportLauncher\s+hidden=\{activeView === "pos"\}/,
    "workspace must hide the launcher on the POS view",
  );
});
