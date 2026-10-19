import test from "node:test";
import assert from "node:assert/strict";

import { heldOrdersForRegister } from "./heldOrders.js";

const registerHeld = { id: "1", source: "pos" };
const onlineOrder = { id: "2", source: "online" };
const qrOrder = { id: "3", source: "qr" };
const preSourceField = { id: "4" };

test("a store with the tables capability sees every held ticket", () => {
  const rows = [registerHeld, onlineOrder, qrOrder, preSourceField];
  assert.deepEqual(heldOrdersForRegister(rows, true), rows);
});

test("a store without tables sees only register-held tickets", () => {
  assert.deepEqual(heldOrdersForRegister([registerHeld, onlineOrder, qrOrder, preSourceField], false), [registerHeld, preSourceField]);
});

test("a missing or malformed list is empty, not a crash", () => {
  assert.deepEqual(heldOrdersForRegister(undefined, false), []);
  assert.deepEqual(heldOrdersForRegister(null, true), []);
  assert.deepEqual(heldOrdersForRegister("nope", false), []);
});
