import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

// Rendering is not available in this suite, so these static checks pin the
// wiring down: the company setting must reach the shared formatter, the
// settings UI must expose it, and printed receipts must honour it.
const read = (path) =>
  readFileSync(new URL(path, import.meta.url), "utf8").replace(/\r\n/g, "\n");

const workspace = read("../features/workspace.jsx");
const settings = read("../features/settings.jsx");
const receipts = read("../features/receipts.jsx");

test("date format: workspace applies the company's choice", () => {
  assert.match(workspace, /setDateFormatConfig\(\{/, "workspace must apply the company date format");
  assert.match(workspace, /dateFormat: workspace\?\.company\?\.date_format/);
  assert.match(workspace, /timeFormat: workspace\?\.company\?\.time_format/);
});

test("date format: settings exposes a Date & time section that saves it", () => {
  assert.match(settings, /label: "Date & time", icon: CalendarDays/, "the section must be listed");
  assert.match(
    settings,
    /onUpdateCompany\(\{ date_format: dateFormat, time_format: timeFormat \}\)/,
    "the card must save both formats through the company update",
  );
});

test("date format: printed receipts use the shared formatter", () => {
  assert.match(receipts, /formatDateTime\(order\.created_at\)/);
  assert.match(receipts, /formatDateTime\(order\.pickup_at\)/);
});

test("country: settings uses the shared country list", () => {
  assert.match(settings, /countryOptions\(fields\.country\)/);
});
