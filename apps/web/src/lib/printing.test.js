import test from "node:test";
import assert from "node:assert/strict";

import {
  CASH_DRAWER_PULSE,
  DEFAULT_QZ_SCRIPT_URL,
  PRINT_DOCUMENT,
  PRINT_METHOD,
  normalizePrintSettings,
  planPrintJob,
  printDocument,
  resolvePrinter,
} from "./printing.js";

test("normalizePrintSettings: defaults to the browser path with safe fields", () => {
  assert.deepEqual(normalizePrintSettings(), {
    method: PRINT_METHOD.BROWSER,
    printers: { receipt: null, invoice: null, "z-report": null, test: null },
    cashDrawer: false,
    scriptUrl: DEFAULT_QZ_SCRIPT_URL,
  });
  // A malformed prefs object must not throw.
  assert.equal(normalizePrintSettings(null).method, PRINT_METHOD.BROWSER);
  assert.equal(normalizePrintSettings("nope").method, PRINT_METHOD.BROWSER);
});

test("normalizePrintSettings: keeps a valid method and trims printer names", () => {
  const settings = normalizePrintSettings({
    print_method: PRINT_METHOD.QZ,
    print_printers: { receipt: "  EPSON TM-T88  ", invoice: "", "z-report": 42 },
    print_cash_drawer: true,
    print_qz_script_url: "  /custom/qz.js  ",
  });
  assert.equal(settings.method, PRINT_METHOD.QZ);
  assert.equal(settings.printers.receipt, "EPSON TM-T88");
  assert.equal(settings.printers.invoice, null);
  assert.equal(settings.printers["z-report"], null);
  assert.equal(settings.printers.test, null);
  assert.equal(settings.cashDrawer, true);
  assert.equal(settings.scriptUrl, "/custom/qz.js");
});

test("normalizePrintSettings: the cash drawer is opt-in, not merely truthy", () => {
  assert.equal(normalizePrintSettings({ print_cash_drawer: "yes" }).cashDrawer, false);
  assert.equal(normalizePrintSettings({ print_cash_drawer: 1 }).cashDrawer, false);
});

test("resolvePrinter: returns the configured name and null when unset", () => {
  const settings = normalizePrintSettings({ print_printers: { receipt: "Front" } });
  assert.equal(resolvePrinter(settings, PRINT_DOCUMENT.RECEIPT), "Front");
  assert.equal(resolvePrinter(settings, PRINT_DOCUMENT.INVOICE), null);
  // Also accepts a raw prefs object.
  assert.equal(resolvePrinter({ print_printers: { invoice: "Back" } }, PRINT_DOCUMENT.INVOICE), "Back");
});

test("planPrintJob: uses QZ only when selected, reachable and there is an element", () => {
  const prefs = {
    print_method: PRINT_METHOD.QZ,
    print_printers: { receipt: "Front" },
    print_cash_drawer: true,
  };
  assert.deepEqual(planPrintJob({ document: PRINT_DOCUMENT.RECEIPT, prefs, qzAvailable: true, hasElement: true }), {
    document: PRINT_DOCUMENT.RECEIPT,
    transport: PRINT_METHOD.QZ,
    printer: "Front",
    cashDrawer: true,
  });
  // No adapter, or nothing to print, falls back to the browser.
  assert.equal(planPrintJob({ prefs, qzAvailable: false, hasElement: true }).transport, PRINT_METHOD.BROWSER);
  assert.equal(planPrintJob({ prefs, qzAvailable: true, hasElement: false }).transport, PRINT_METHOD.BROWSER);
});

test("planPrintJob: the drawer only fires for receipts, never invoices", () => {
  const prefs = { print_method: PRINT_METHOD.QZ, print_cash_drawer: true };
  assert.equal(planPrintJob({ document: PRINT_DOCUMENT.INVOICE, prefs, qzAvailable: true }).cashDrawer, false);
  assert.equal(planPrintJob({ document: PRINT_DOCUMENT.RECEIPT, prefs, qzAvailable: true }).cashDrawer, true);
});

test("planPrintJob: browser and kiosk methods never plan a QZ job", () => {
  for (const method of [PRINT_METHOD.BROWSER, PRINT_METHOD.KIOSK]) {
    assert.equal(planPrintJob({ prefs: { print_method: method }, qzAvailable: true }).transport, PRINT_METHOD.BROWSER);
  }
});

test("planPrintJob: an unknown document kind degrades to a receipt", () => {
  assert.equal(planPrintJob({ document: "bogus" }).document, PRINT_DOCUMENT.RECEIPT);
});

test("printDocument: sends a QZ job with printer and drawer, then reports ok", async () => {
  const calls = [];
  const result = await printDocument({
    document: PRINT_DOCUMENT.RECEIPT,
    prefs: { print_method: PRINT_METHOD.QZ, print_printers: { receipt: "Front" }, print_cash_drawer: true },
    element: { id: "sheet" },
    qz: { isAvailable: true, print: async (job) => calls.push(job) },
    fallback: async () => "browser",
  });
  assert.deepEqual(calls, [{ document: PRINT_DOCUMENT.RECEIPT, element: { id: "sheet" }, printer: "Front", cashDrawer: true }]);
  assert.equal(result.ok, true);
  assert.equal(result.transport, PRINT_METHOD.QZ);
});

test("printDocument: a QZ failure falls back to the browser without throwing", async () => {
  let fellBack = 0;
  let notified = null;
  const result = await printDocument({
    document: PRINT_DOCUMENT.RECEIPT,
    prefs: { print_method: PRINT_METHOD.QZ },
    element: { id: "sheet" },
    qz: { isAvailable: () => true, print: async () => { throw new Error("QZ offline"); } },
    fallback: async () => { fellBack += 1; return "browser"; },
    onFallback: (error) => { notified = error; },
  });
  assert.equal(fellBack, 1);
  assert.equal(notified.message, "QZ offline");
  assert.equal(result.ok, false);
  assert.equal(result.transport, PRINT_METHOD.BROWSER);
  assert.equal(result.fallback, "browser");
});

test("printDocument: runs the browser fallback directly when QZ is not planned", async () => {
  let called = 0;
  const qz = { isAvailable: true, print: async () => { throw new Error("must not be used"); } };
  const result = await printDocument({
    document: PRINT_DOCUMENT.RECEIPT,
    prefs: {}, // browser method
    element: { id: "sheet" },
    qz,
    fallback: async () => { called += 1; return "browser"; },
  });
  assert.equal(called, 1);
  assert.equal(result.ok, true);
  assert.equal(result.transport, PRINT_METHOD.BROWSER);
});

test("CASH_DRAWER_PULSE is the ESC/POS pin-0 pulse", () => {
  assert.deepEqual(CASH_DRAWER_PULSE, [0x1b, 0x70, 0x00, 0x19, 0xfa]);
});
