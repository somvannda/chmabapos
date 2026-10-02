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

test("buildNudges: adds a shift nudge when the store requires an open shift", () => {
  const nudges = buildNudges(null, [], { requireOpenShift: true, hasOpenShift: false });
  assert.equal(nudges.length, 1);
  assert.equal(nudges[0].id, "shift");
  assert.equal(nudges[0].href, "pos");
  assert.match(nudges[0].label, /open a shift/i);
});

test("buildNudges: hides the shift nudge when a shift is open", () => {
  assert.deepEqual(buildNudges(null, [], { requireOpenShift: true, hasOpenShift: true }), []);
});

test("buildNudges: hides the shift nudge when a shift is not required", () => {
  assert.deepEqual(buildNudges(null, [], { requireOpenShift: false, hasOpenShift: false }), []);
});

test("buildNudges: hides the shift nudge when no shift info is provided", () => {
  assert.deepEqual(buildNudges(null, []), []);
});

test("buildNudges: does not duplicate the setup open-shift step", () => {
  const checklist = {
    completed: 0,
    total: 2,
    steps: [
      { id: "open-shift", done: false, title: "Open a shift", href: "dashboard" },
      { id: "first-sale", done: false, title: "Ring up your first sale", href: "pos" },
    ],
  };
  const nudges = buildNudges(checklist, [], { requireOpenShift: true, hasOpenShift: false });
  assert.deepEqual(nudges.map((nudge) => nudge.id), ["setup"]);
  assert.equal(nudges[0].label, "Open a shift");
});

test("buildNudges: orders the shift nudge before restock", () => {
  const nudges = buildNudges(null, [{ id: 1 }], { requireOpenShift: true, hasOpenShift: false });
  assert.deepEqual(nudges.map((nudge) => nudge.id), ["shift", "restock"]);
});
