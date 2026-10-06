import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

// Guards a real regression: a reservation is only partly paid, but taking a
// deposit printed the ordinary full-sale receipt. A reservation must instead
// produce a deposit receipt that shows the outstanding balance. Rendering is
// not available in this suite, so these static checks pin the wiring down.
const receipts = readFileSync(
  new URL("../features/receipts.jsx", import.meta.url),
  "utf8",
).replace(/\r\n/g, "\n");
const workspace = readFileSync(
  new URL("../features/workspace.jsx", import.meta.url),
  "utf8",
).replace(/\r\n/g, "\n");

test("deposit receipt: the print sheet uses the deposit body for reservations", () => {
  assert.match(
    receipts,
    /function ReceiptPrintSheet\(\{ order, workspace \}\)[\s\S]*?order\.status === "pending_pickup"[\s\S]*?<DepositReceiptBody/,
    "ReceiptPrintSheet must print a deposit receipt for pending_pickup orders",
  );
});

test("deposit receipt: the preview modal uses the deposit body for reservations", () => {
  assert.match(
    receipts,
    /const isDeposit = order\.status === "pending_pickup"/,
    "ReceiptModal must detect a reservation from the order status",
  );
  assert.match(
    receipts,
    /if \(isDeposit\) \{[\s\S]*?<DepositReceiptBody/,
    "ReceiptModal must preview the deposit receipt for reservations",
  );
});

test("deposit receipt: the body shows the outstanding balance", () => {
  assert.match(
    receipts,
    /function DepositReceiptBody[\s\S]*?Balance due[\s\S]*?formatCurrencyAmount\(balance/,
    "the deposit receipt must show the balance still due",
  );
});

test("deposit receipt: taking a deposit does not toast a completed sale", () => {
  assert.match(
    workspace,
    /if \(order\.status !== "pending_pickup"\) notify\(`\$\{order\.order_number\} completed`\)/,
    "a reservation must not be announced as a completed sale",
  );
});
