import test from "node:test";
import assert from "node:assert/strict";

import { buildDisplaySnapshot, DISPLAY_STATUS } from "./customerDisplay.js";

test("snapshot: normalizes lines and computes line totals", () => {
  const snapshot = buildDisplaySnapshot({
    storeName: "Main Counter",
    currency: "USD",
    items: [
      { id: "p1", name: "Coffee", quantity: 2, price: "3.50" },
      { lineKey: "p2:v1", name: "Cake", quantity: 1, unitPrice: 4 },
    ],
    subtotal: 11,
    total: 11,
  });
  assert.equal(snapshot.storeName, "Main Counter");
  assert.equal(snapshot.items[0].key, "p1");
  assert.equal(snapshot.items[0].lineTotal, 7);
  assert.equal(snapshot.items[1].key, "p2:v1");
  assert.equal(snapshot.items[1].unitPrice, 4);
});

test("snapshot: item count multiplies by quantity", () => {
  const snapshot = buildDisplaySnapshot({
    items: [
      { id: "a", name: "A", quantity: 3, price: 1 },
      { id: "b", name: "B", quantity: 2, price: 1 },
    ],
  });
  assert.equal(snapshot.itemCount, 5);
});

test("snapshot: payment details are normalized, otherwise null", () => {
  const withPayment = buildDisplaySnapshot({
    currency: "KHR",
    total: 12000,
    status: DISPLAY_STATUS.PAYMENT,
    payment: { qrString: "00020101", amount: "12000", currency: "KHR", externalId: "ext-1" },
  });
  assert.equal(withPayment.payment.qrString, "00020101");
  assert.equal(withPayment.payment.amount, 12000);
  assert.equal(withPayment.payment.externalId, "ext-1");

  const withoutPayment = buildDisplaySnapshot({ total: 5 });
  assert.equal(withoutPayment.payment, null);
});

test("snapshot: tolerates junk input and defaults to idle", () => {
  const snapshot = buildDisplaySnapshot({
    items: [
      { quantity: -2, price: "abc" },
      null,
    ],
    subtotal: "not-a-number",
    status: undefined,
  });
  assert.equal(snapshot.items.length, 2);
  assert.equal(snapshot.items[0].quantity, 0);
  assert.equal(snapshot.subtotal, 0);
  assert.equal(snapshot.status, DISPLAY_STATUS.IDLE);
  assert.equal(snapshot.currency, "USD");
});

test("snapshot: prices are rounded to cents", () => {
  const snapshot = buildDisplaySnapshot({
    items: [{ id: "a", name: "A", quantity: 3, price: 0.1 }],
  });
  assert.equal(snapshot.items[0].lineTotal, 0.3);
});
