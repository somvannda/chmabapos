import test from "node:test";
import assert from "node:assert/strict";

import { OFFLINE_ORDERS_KEY, enqueueOfflineOrder, flushOfflineOrders, isRetryable, loadOfflineOrders } from "./offlineQueue.js";

function fakeStorage() {
  const map = new Map();
  return {
    getItem: (key) => (map.has(key) ? map.get(key) : null),
    setItem: (key, value) => map.set(key, String(value)),
    removeItem: (key) => map.delete(key),
  };
}

test("offlineQueue: enqueues and loads orders", () => {
  const storage = fakeStorage();
  assert.deepEqual(loadOfflineOrders(storage), []);
  const count = enqueueOfflineOrder("store-1", { items: [], client_order_id: "x" }, storage);
  assert.equal(count, 1);
  assert.equal(loadOfflineOrders(storage).length, 1);
});

test("offlineQueue: tolerates corrupt storage", () => {
  const storage = fakeStorage();
  storage.setItem(OFFLINE_ORDERS_KEY, "{not json");
  assert.deepEqual(loadOfflineOrders(storage), []);
});

test("offlineQueue: flushes successes, keeps retryable failures, drops validation failures", async () => {
  const storage = fakeStorage();
  enqueueOfflineOrder("s", { client_order_id: "ok" }, storage);
  enqueueOfflineOrder("s", { client_order_id: "net" }, storage);
  enqueueOfflineOrder("s", { client_order_id: "bad" }, storage);
  const createOrder = async (_token, _storeId, body) => {
    if (body.client_order_id === "net") throw new Error("failed to fetch");
    if (body.client_order_id === "bad") {
      const error = new Error("invalid");
      error.status = 422;
      throw error;
    }
    return {};
  };
  const result = await flushOfflineOrders({ token: "t", createOrder, storage });
  assert.deepEqual(result, { flushed: 1, failed: 1, remaining: 1 });
  const left = loadOfflineOrders(storage);
  assert.equal(left.length, 1);
  assert.equal(left[0].body.client_order_id, "net");
});

test("offlineQueue: classifies retryable errors", () => {
  assert.equal(isRetryable(new Error("failed to fetch")), true);
  assert.equal(isRetryable({ status: undefined }), true);
  assert.equal(isRetryable({ status: 500 }), true);
  assert.equal(isRetryable({ status: 401 }), true);
  assert.equal(isRetryable({ status: 422 }), false);
  assert.equal(isRetryable({ status: 409 }), false);
});
