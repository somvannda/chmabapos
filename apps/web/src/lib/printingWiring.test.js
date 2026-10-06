import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

// Rendering is not available in this suite, so these static checks pin the
// settings surface down: the POS preferences must let a store choose the print
// method, map printers per document and opt into the cash drawer. The values are
// read by lib/printing.js and carried into a QZ job by lib/qzTray.js.
const read = (path) =>
  readFileSync(new URL(path, import.meta.url), "utf8").replace(/\r\n/g, "\n");

const settings = read("../features/settings.jsx");

test("printing settings: the POS preferences expose the print method", () => {
  assert.match(settings, /value: "browser", label: "Browser dialog"[\s\S]*?value: "qz", label: "QZ Tray"/, "a store must be able to choose the QZ Tray transport");
  assert.match(settings, /print_method: value/, "the control must write print_method");
});

test("printing settings: printers are mapped per document and stored normalized", () => {
  assert.match(settings, /\["browser", "kiosk", "qz"\]\.includes\(prefs\.print_method\)/, "an unknown stored method must fall back to browser");
  assert.match(settings, /print_printers: \{ receipt: "", invoice: "", "z-report": ""/, "the three document printers must be collected");
});

test("printing settings: the cash drawer is an explicit opt-in", () => {
  assert.match(settings, /print_cash_drawer: Boolean\(prefs\.print_cash_drawer\)/, "the stored drawer flag must be boolean");
  assert.match(settings, /print_cash_drawer: event\.target\.checked/, "the toggle must write print_cash_drawer");
});
