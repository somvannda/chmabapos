import test from "node:test";
import assert from "node:assert/strict";

import {
  formatDate,
  formatDateTime,
  formatDateWith,
  formatTimeWith,
  getDateFormatConfig,
  setDateFormatConfig,
  subscribeDateFormat,
  toDate,
} from "./dateFormat.js";

// A fixed local moment so the assertions never depend on the machine's timezone.
const MOMENT = new Date(2026, 11, 31, 18, 5, 0); // 31 Dec 2026, 18:05 local

test("formatDateWith renders each supported date pattern", () => {
  assert.equal(formatDateWith(MOMENT, "DD/MM/YYYY"), "31/12/2026");
  assert.equal(formatDateWith(MOMENT, "MM/DD/YYYY"), "12/31/2026");
  assert.equal(formatDateWith(MOMENT, "YYYY-MM-DD"), "2026-12-31");
  assert.equal(formatDateWith(MOMENT, "D MMM YYYY"), "31 Dec 2026");
});

test("formatTimeWith renders 12-hour and 24-hour styles", () => {
  assert.equal(formatTimeWith(MOMENT, "24h"), "18:05");
  assert.equal(formatTimeWith(MOMENT, "12h"), "6:05 PM");
  assert.equal(formatTimeWith(new Date(2026, 0, 1, 0, 0, 0), "12h"), "12:00 AM");
  assert.equal(formatTimeWith(new Date(2026, 0, 1, 12, 0, 0), "12h"), "12:00 PM");
});

test("toDate keeps a bare date string on the local calendar day", () => {
  const parsed = toDate("2026-12-31");
  assert.equal(parsed.getFullYear(), 2026);
  assert.equal(parsed.getMonth(), 11);
  assert.equal(parsed.getDate(), 31);
});

test("toDate returns null for missing or invalid values", () => {
  assert.equal(toDate(null), null);
  assert.equal(toDate(undefined), null);
  assert.equal(toDate(""), null);
  assert.equal(toDate("not-a-date"), null);
});

test("the active config drives formatDate and formatDateTime", () => {
  setDateFormatConfig({ dateFormat: "YYYY-MM-DD", timeFormat: "24h" });
  assert.equal(formatDate(MOMENT), "2026-12-31");
  assert.equal(formatDateTime(MOMENT), "2026-12-31 18:05");

  // Empty config falls back to device formatting rather than a fixed pattern.
  setDateFormatConfig({ dateFormat: "", timeFormat: "" });
  assert.equal(formatDate(MOMENT), MOMENT.toLocaleDateString());
  assert.equal(formatDateTime(MOMENT), MOMENT.toLocaleString());
  assert.deepEqual(getDateFormatConfig(), { dateFormat: "", timeFormat: "" });
});

test("subscribeDateFormat notifies on change and stops after unsubscribe", () => {
  setDateFormatConfig({ dateFormat: "", timeFormat: "" });
  let calls = 0;
  const unsubscribe = subscribeDateFormat(() => {
    calls += 1;
  });
  setDateFormatConfig({ dateFormat: "D MMM YYYY", timeFormat: "12h" });
  assert.equal(calls, 1);
  // A no-op set must not notify again.
  setDateFormatConfig({ dateFormat: "D MMM YYYY", timeFormat: "12h" });
  assert.equal(calls, 1);
  unsubscribe();
  setDateFormatConfig({ dateFormat: "", timeFormat: "" });
  assert.equal(calls, 1);
});

test("formatDate and formatDateTime return empty text for invalid input", () => {
  assert.equal(formatDate(null), "");
  assert.equal(formatDateTime("nonsense"), "");
});
