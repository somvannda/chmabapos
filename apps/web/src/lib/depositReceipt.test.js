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
const sales = readFileSync(
  new URL("../features/sales.jsx", import.meta.url),
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

test("pickup collect: a settled balance prints the final receipt", () => {
  assert.match(
    workspace,
    /const finalizeCollectedOrder = \(order\) => \{[\s\S]*?auto_print_receipt !== false[\s\S]*?printOrderReceipt\(order\)/,
    "collecting a balance must print the final receipt per the auto-print setting",
  );
  assert.match(
    workspace,
    /updated\.status === "paid"\) finalizeCollectedOrder\(updated\)/,
    "a cash balance that settles immediately must print the receipt",
  );
});

test("pickup collect: a KHQR balance prints the receipt once it settles", () => {
  assert.match(
    sales,
    /function CollectBalanceModal\(\{[^}]*onSettled[^}]*\}\)/,
    "CollectBalanceModal must accept an onSettled callback",
  );
  assert.match(
    sales,
    /api\.order\(token, storeId, order\.id\)[\s\S]*?status === "paid"[\s\S]*?onSettled\(fresh\)/,
    "the balance QR must poll until paid and then hand off for printing",
  );
  assert.match(
    workspace,
    /onConfirm=\{collectBalance\} token=\{token\} storeId=\{storeId\} onSettled=\{handleBalanceSettled\}/,
    "workspace must pass the settlement handler into the collect modal",
  );
});
