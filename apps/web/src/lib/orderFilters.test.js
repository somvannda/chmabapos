import test from "node:test";
import assert from "node:assert/strict";

import { buildOrderQuery, orderRangeDates } from "./orderFilters.js";

const NOW = new Date(2026, 9, 13); // 2026-10-13

test("orderRangeDates returns inclusive ISO bounds for each preset", () => {
  assert.deepEqual(orderRangeDates("today", NOW), { from: "2026-10-13", to: "2026-10-13" });
  assert.deepEqual(orderRangeDates("7d", NOW), { from: "2026-10-07", to: "2026-10-13" });
  assert.deepEqual(orderRangeDates("30d", NOW), { from: "2026-09-14", to: "2026-10-13" });
  assert.deepEqual(orderRangeDates("month", NOW), { from: "2026-10-01", to: "2026-10-13" });
  assert.deepEqual(orderRangeDates("all", NOW), { from: null, to: null });
});

test("buildOrderQuery omits defaults and applies the limit", () => {
  assert.deepEqual(buildOrderQuery({}, NOW), { limit: 50 });
  assert.deepEqual(buildOrderQuery({ status: "all", search: "   ", range: "all" }, NOW), { limit: 50 });
});

test("buildOrderQuery maps filters to the API params", () => {
  assert.deepEqual(
    buildOrderQuery({ status: "paid", search: "  ORD-12  ", range: "7d", limit: 20 }, NOW),
    { limit: 20, status: "paid", search: "ORD-12", from_date: "2026-10-07", to_date: "2026-10-13" },
  );
});
