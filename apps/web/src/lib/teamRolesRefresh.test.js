import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

// Guards a real regression: creating a role in the "Roles & permissions" card
// must refresh the invite dialog's role list immediately, without a browser
// reload. The team view and the roles card hold separate role state, so the
// card has to notify its parent when roles change. Rendering is not available
// in this suite, so this static check pins the wiring down.
const read = (path) =>
  readFileSync(new URL(path, import.meta.url), "utf8").replace(/\r\n/g, "\n");

const team = read("../features/team.jsx");
const roles = read("../features/roles.jsx");

test("team roles refresh: the roles card notifies its parent", () => {
  assert.match(
    roles,
    /function RolesCard\(\{[^}]*onRolesChanged[^}]*\}\)/,
    "RolesCard must accept an onRolesChanged callback",
  );
  assert.match(
    roles,
    /onRolesChanged\?\.\(\)/,
    "RolesCard must invoke onRolesChanged after saving or deleting a role",
  );
});

test("team roles refresh: the team view passes its loader to the roles card", () => {
  assert.match(
    team,
    /const loadRoles\s*=\s*async\s*\(\)\s*=>/,
    "the team view must define a reusable roles loader",
  );
  assert.match(
    team,
    /<RolesCard[^>]*onRolesChanged=\{loadRoles\}/,
    "the team view must pass loadRoles to RolesCard so invites see new roles",
  );
});
