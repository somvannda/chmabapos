import test from "node:test";
import assert from "node:assert/strict";

import { VIEW_ROLES, canViewRole } from "./roleViews.js";

const ALL_ROLES = ["owner", "manager", "inventory_manager", "cashier"];

test("every view allows at least one known role", () => {
  for (const [view, roles] of Object.entries(VIEW_ROLES)) {
    assert.ok(roles.length > 0, `${view} must allow at least one role`);
    for (const role of roles) assert.ok(ALL_ROLES.includes(role), `${view} has unknown role ${role}`);
  }
});

test("owner can open every view", () => {
  for (const view of Object.keys(VIEW_ROLES)) {
    assert.equal(canViewRole("owner", view), true, `owner should reach ${view}`);
  }
});

test("team and billing stay owner-only", () => {
  for (const view of ["team", "billing"]) {
    assert.deepEqual(VIEW_ROLES[view], ["owner"]);
    assert.equal(canViewRole("manager", view), false);
    assert.equal(canViewRole("cashier", view), false);
  }
});

test("cashier is confined to selling and support surfaces", () => {
  assert.equal(canViewRole("cashier", "pos"), true);
  assert.equal(canViewRole("cashier", "orders"), true);
  assert.equal(canViewRole("cashier", "help"), true);
  assert.equal(canViewRole("cashier", "products"), false);
  assert.equal(canViewRole("cashier", "inventory"), false);
  assert.equal(canViewRole("cashier", "approvals"), false);
});

test("an unknown role or view is denied", () => {
  assert.equal(canViewRole("ghost", "pos"), false);
  assert.equal(canViewRole("owner", "nope"), false);
  assert.equal(canViewRole(undefined, "pos"), false);
});
