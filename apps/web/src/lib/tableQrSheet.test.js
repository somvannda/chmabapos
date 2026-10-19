import test from "node:test";
import assert from "node:assert/strict";

import { escapeHtml, tableQrSheetHtml } from "./tableQrSheet.js";

test("one card per table, each with its code and name", () => {
  const html = tableQrSheetHtml({
    storeName: "Corner Cafe",
    tables: [
      { id: "1", name: "T1", qrSvg: "<svg data-qr='1'></svg>" },
      { id: "2", name: "Window 2", qrSvg: "<svg data-qr='2'></svg>" },
    ],
  });
  assert.equal((html.match(/class="card"/g) || []).length, 2);
  assert.match(html, /data-qr='1'/);
  assert.match(html, /Window 2/);
  assert.match(html, /Scan to order from your table/);
  assert.match(html, /Corner Cafe/);
});

test("a table with no rendered code still prints its card", () => {
  const html = tableQrSheetHtml({ storeName: "S", tables: [{ id: "1", name: "T1", qrSvg: "" }] });
  assert.equal((html.match(/class="card"/g) || []).length, 1);
});

test("an empty list renders no cards", () => {
  const html = tableQrSheetHtml({ storeName: "S", tables: [] });
  assert.equal((html.match(/class="card"/g) || []).length, 0);
  assert.equal(tableQrSheetHtml().includes('class="card"'), false);
});

test("a table name cannot inject markup", () => {
  assert.equal(escapeHtml('<script>x</script>'), "&lt;script&gt;x&lt;/script&gt;");
  const html = tableQrSheetHtml({ storeName: "S", tables: [{ id: "1", name: '<img src=x onerror=1>', qrSvg: "" }] });
  assert.equal(html.includes("<img src=x onerror=1>"), false);
  assert.match(html, /&lt;img src=x onerror=1&gt;/);
});
