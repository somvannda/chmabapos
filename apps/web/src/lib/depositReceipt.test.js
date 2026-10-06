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

test("deposit receipt: reservations show a deposit note on the regular template", () => {
  assert.match(
    receipts,
    /function ReservationNote[\s\S]*?Deposit receipt[\s\S]*?Deposit paid[\s\S]*?Balance due/,
    "the reservation note must be labelled as a deposit receipt with the deposit and balance",
  );
  assert.match(
    receipts,
    /function ReceiptProfessionalBody[\s\S]*?<ReservationNote[\s\S]*?function ReceiptClassicBody[\s\S]*?<ReservationNote/,
    "both regular templates must append the deposit note for reservations",
  );
});

test("deposit receipt: the print sheet and preview use the regular template", () => {
  assert.match(
    receipts,
    /function ReceiptPrintSheet\(\{ order, workspace \}\)[\s\S]*?<ReceiptSheetBody/,
    "the print sheet must render the store's regular receipt body",
  );
  assert.match(
    receipts,
    /function DepositReceiptSheet[\s\S]*?return <ReceiptPrintSheet/,
    "the deposit print path must reuse the regular print sheet",
  );
  assert.doesNotMatch(
    receipts,
    /DepositReceiptBody/,
    "the bespoke deposit layout must be gone in favour of the regular template",
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

test("pickup collect: switching to KHQR clears the prefilled cash so a QR is raised", () => {
  // Guards a real regression: the collect modal prefilled "Cash received" with
  // the whole balance, so ticking "Collect the rest by KHQR" left no remainder,
  // raised no QR and silently collected the balance as cash.
  assert.match(
    sales,
    /const toggleKhqr = \(checked\) => \{[\s\S]*?setAmount\(\(current\) => \(checked \? \(Number\(current\) >= balance \? "" : current\) : balance\.toFixed\(2\)\)\)/,
    "enabling KHQR must clear a cash amount that already covers the balance",
  );
  assert.match(
    sales,
    /checked=\{useKhqr\} onChange=\{\(event\) => toggleKhqr\(event\.target\.checked\)\}/,
    "the collect modal checkbox must use the KHQR toggle handler",
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
