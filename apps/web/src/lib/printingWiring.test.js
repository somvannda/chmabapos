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
const workspace = read("../features/workspace.jsx");
const api = read("../api.js");

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

test("printing wiring: receipts print through printDocument with a browser fallback", () => {
  assert.match(workspace, /const printViaSheet = \(order, setOrder, kind\)/, "the register must route print sheets through one helper");
  assert.match(workspace, /await printDocument\(\{[\s\S]*?fallback: \(\) => window\.print\(\)/, "printing must fall back to window.print()");
  assert.match(workspace, /qz: settings\.method === "qz" \? qzTransport\(settings\.scriptUrl\) : null/, "QZ is only used when the store chose it");
  assert.match(workspace, /const printOrderReceipt = \(order\) => printViaSheet\(order, setPrintOrder, "receipt"\)/, "receipts must use the helper");
  assert.match(workspace, /const printDepositReceipt = \(order\) => printViaSheet\(order, setDepositPrintOrder, "receipt"\)/, "deposit receipts must use the helper");
});

test("printing wiring: the QZ transport is built from the signing API", () => {
  assert.match(workspace, /createQzTransport\(\{ scriptUrl, certificate: \(\) => api\.qzCertificate\(token\), sign: \(toSign\) => api\.qzSign\(token, toSign\)/, "the adapter must be wired to the certificate/sign endpoints");
  assert.match(api, /qzCertificate: \(token\) => request\("\/printing\/qz\/certificate", \{ token \}\)/, "api must expose the certificate endpoint");
  assert.match(api, /qzSign: \(token, toSign\) => request\("\/printing\/qz\/sign", \{ \.\.\.json\("POST", \{ request: toSign \}\), token \}\)/, "api must expose the sign endpoint");
});
