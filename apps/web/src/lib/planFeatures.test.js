import test from "node:test";
import assert from "node:assert/strict";

import { PLAN_FEATURES, hasPlanFeature } from "./planFeatures.js";

test("the catalog covers the backend feature keys the UI gates on", () => {
  for (const key of ["inventory_management", "purchasing", "advanced_reports", "loyalty", "table_management", "refunds", "held_orders", "shift_management", "multi_currency", "email_receipts"]) {
    assert.ok(PLAN_FEATURES.includes(key), `missing plan feature: ${key}`);
  }
});

test("hasPlanFeature is true only for an included key", () => {
  const plan = ["inventory_management", "held_orders"];
  assert.equal(hasPlanFeature(plan, "held_orders"), true);
  assert.equal(hasPlanFeature(plan, "refunds"), false);
});

test("hasPlanFeature is strict when the plan is unknown", () => {
  // Unlike capability packs, a missing/loading plan must not show a paid
  // control that the backend would reject with 403.
  assert.equal(hasPlanFeature(null, "held_orders"), false);
  assert.equal(hasPlanFeature(undefined, "table_management"), false);
  assert.equal(hasPlanFeature([], "advanced_reports"), false);
});
