import test from "node:test";
import assert from "node:assert/strict";

import {
  OFFLINE_FAILED_KEY,
  OFFLINE_ORDERS_KEY,
  dismissFailedOrder,
  enqueueOfflineOrder,
  flushOfflineOrders,
  isOfflineQueuable,
  isRetryable,
  loadFailedOrders,
  loadOfflineOrders,
  retryFailedOrder,
  rowKey,
} from "./offlineQueue.js";

function fakeStorage() {
  const map = new Map();
  return {
    getItem: (key) => (map.has(key) ? map.get(key) : null),
    setItem: (key, value) => map.set(key, String(value)),
    removeItem: (key) => map.delete(key),
  };
}

function failingCreateOrder(bodyErrors) {
  return async (_token, _storeId, body) => {
    const kind = bodyErrors[body.client_order_id];
    if (kind === "network") throw new Error("failed to fetch");
    if (typeof kind === "number") {
      const error = new Error("invalid");
      error.status = kind;
      throw error;
    }
    return {};
  };
}

test("offlineQueue: enqueues and loads orders", () => {
  const storage = fakeStorage();
  assert.deepEqual(loadOfflineOrders(storage), []);
  const count = enqueueOfflineOrder("store-1", { items: [], client_order_id: "x" }, storage);
  assert.equal(count, 1);
  const rows = loadOfflineOrders(storage);
  assert.equal(rows.length, 1);
  assert.equal(typeof rows[0].id, "string");
  assert.ok(rows[0].id.length > 0);
});

test("offlineQueue: tolerates corrupt storage", () => {
  const storage = fakeStorage();
  storage.setItem(OFFLINE_ORDERS_KEY, "{not json");
  storage.setItem(OFFLINE_FAILED_KEY, "{not json");
  assert.deepEqual(loadOfflineOrders(storage), []);
  assert.deepEqual(loadFailedOrders(storage), []);
});

test("offlineQueue: flush removes successes, keeps retryable failures, files validation failures", async () => {
  const storage = fakeStorage();
  enqueueOfflineOrder("s", { client_order_id: "ok" }, storage);
  enqueueOfflineOrder("s", { client_order_id: "net" }, storage);
  enqueueOfflineOrder("s", { client_order_id: "bad" }, storage);
  const createOrder = failingCreateOrder({ net: "network", bad: 422 });
  const result = await flushOfflineOrders({ token: "t", createOrder, storage });
  assert.deepEqual(result, { flushed: 1, failed: 1, remaining: 1 });
  const queued = loadOfflineOrders(storage);
  assert.equal(queued.length, 1);
  assert.equal(queued[0].body.client_order_id, "net");
  const failed = loadFailedOrders(storage);
  assert.equal(failed.length, 1);
  assert.equal(failed[0].body.client_order_id, "bad");
  assert.equal(failed[0].error, "invalid");
});

test("offlineQueue: dismissFailedOrder drops one failed sale", async () => {
  const storage = fakeStorage();
  enqueueOfflineOrder("s", { client_order_id: "bad" }, storage);
  await flushOfflineOrders({ token: "t", createOrder: failingCreateOrder({ bad: 422 }), storage });
  const failed = loadFailedOrders(storage);
  assert.equal(failed.length, 1);
  const left = dismissFailedOrder(rowKey(failed[0]), storage);
  assert.equal(left.length, 0);
  assert.deepEqual(loadFailedOrders(storage), []);
});

test("offlineQueue: retryFailedOrder moves a failed sale back onto the queue", async () => {
  const storage = fakeStorage();
  enqueueOfflineOrder("s", { client_order_id: "bad" }, storage);
  await flushOfflineOrders({ token: "t", createOrder: failingCreateOrder({ bad: 422 }), storage });
  const failed = loadFailedOrders(storage);
  const result = retryFailedOrder(rowKey(failed[0]), storage);
  assert.deepEqual(result, { queued: 1, failed: 0 });
  const queued = loadOfflineOrders(storage);
  assert.equal(queued.length, 1);
  assert.equal(queued[0].body.client_order_id, "bad");
  assert.equal(queued[0].error, undefined);
  assert.equal(queued[0].failedAt, undefined);
});

test("offlineQueue: classifies retryable errors", () => {
  assert.equal(isRetryable(new Error("failed to fetch")), true);
  assert.equal(isRetryable({ status: undefined }), true);
  assert.equal(isRetryable({ status: 500 }), true);
  assert.equal(isRetryable({ status: 401 }), true);
  assert.equal(isRetryable({ status: 422 }), false);
  assert.equal(isRetryable({ status: 409 }), false);
});

test("offlineQueue: only cash / trade-in sales are offline-queuable", () => {
  assert.equal(isOfflineQueuable([{ method: "cash" }]), true);
  assert.equal(isOfflineQueuable([{ method: "cash" }, { method: "trade_in" }]), true);
  assert.equal(isOfflineQueuable([]), true);
  assert.equal(isOfflineQueuable(undefined), true);
  assert.equal(isOfflineQueuable([{ method: "khqr" }]), false);
  assert.equal(isOfflineQueuable([{ method: "card" }]), false);
  assert.equal(isOfflineQueuable([{ method: "cash" }, { method: "khqr" }]), false);
});

test("offlineQueue: flush does not duplicate an already-filed failure", async () => {
  const storage = fakeStorage();
  enqueueOfflineOrder("s", { client_order_id: "bad" }, storage);
  const queued = loadOfflineOrders(storage)[0];
  // Simulate a previous (possibly overlapping) flush having already filed this row.
  storage.setItem(OFFLINE_FAILED_KEY, JSON.stringify([{ ...queued, error: "already filed", failedAt: 1 }]));
  await flushOfflineOrders({ token: "t", createOrder: failingCreateOrder({ bad: 422 }), storage });
  const failed = loadFailedOrders(storage);
  assert.equal(failed.length, 1);
  assert.equal(failed[0].body.client_order_id, "bad");
  assert.deepEqual(loadOfflineOrders(storage), []);
});
