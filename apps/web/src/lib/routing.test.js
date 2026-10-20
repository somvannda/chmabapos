import test from "node:test";
import assert from "node:assert/strict";

import { VIEW_ROLES } from "./roleViews.js";
import { parseRoute, userPath, viewFromPath } from "../routing.js";

const user = { email: "nadia@cedarstone.co", full_name: "Nadia Sok" };

test("every workspace view round-trips through its URL", () => {
  // Regression: floor, kitchen, deliveries and approvals were missing from the
  // view <-> page maps. `userPath` fell back to /<user>/dashboard, and the
  // location effect parsed that back to the dashboard - so the first click on
  // Deliveries appeared to bounce straight back to Overview.
  for (const view of Object.keys(VIEW_ROLES)) {
    const path = userPath(user, view);
    assert.equal(parseRoute(path).view, view, `${view} is missing from USER_PAGE_TO_VIEW`);
    assert.equal(viewFromPath(path), view, `${view} does not round-trip through userPath`);
  }
});

test("unknown views still fall back to the dashboard", () => {
  assert.equal(userPath(user, "nope"), userPath(user, "dashboard"));
  assert.equal(viewFromPath("/nadia/nope"), "dashboard");
});
