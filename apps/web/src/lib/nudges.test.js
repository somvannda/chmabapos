import test from "node:test";
import assert from "node:assert/strict";

import { buildNudges } from "./nudges.js";

const steps = [
  { done: true, title: "Add products", href: "products" },
  { done: false, title: "Open a shift", description: "Start a register session.", href: "dashboard" },
  { done: false, title: "Ring up your first sale", href: "pos" },
];

test("buildNudges: surfaces the next incomplete setup step", () => {
  const nudges = buildNudges({ completed: 1, total: 3, steps }, []);
  assert.equal(nudges.length, 1);
  assert.equal(nudges[0].id, "setup");
  assert.equal(nudges[0].label, "Open a shift");
  assert.equal(nudges[0].description, "Start a register session.");
  assert.equal(nudges[0].href, "dashboard");
});

test("buildNudges: adds a low-stock nudge for multiple items", () => {
  const nudges = buildNudges(null, [{ id: 1 }, { id: 2 }]);
  assert.equal(nudges.length, 1);
  assert.equal(nudges[0].id, "restock");
  assert.equal(nudges[0].label, "2 items low on stock");
  assert.equal(nudges[0].href, "inventory");
});

test("buildNudges: uses the singular form for a single low item", () => {
  const nudges = buildNudges(null, [{ id: 1 }]);
  assert.equal(nudges[0].label, "1 item low on stock");
});

test("buildNudges: combines setup and restock nudges", () => {
  const nudges = buildNudges({ completed: 1, total: 3, steps }, [{ id: 1 }]);
  assert.deepEqual(nudges.map((nudge) => nudge.id), ["setup", "restock"]);
});

test("buildNudges: returns nothing when setup is complete and stock is fine", () => {
  assert.deepEqual(buildNudges({ completed: 3, total: 3, steps }, []), []);
});

test("buildNudges: tolerates missing checklist and low stock", () => {
  assert.deepEqual(buildNudges(null, null), []);
  assert.deepEqual(buildNudges(undefined, undefined), []);
});

test("buildNudges: falls back to the dashboard when a step has no href", () => {
  const nudges = buildNudges({ completed: 0, total: 1, steps: [{ done: false, title: "Start" }] }, []);
  assert.equal(nudges[0].href, "dashboard");
});
